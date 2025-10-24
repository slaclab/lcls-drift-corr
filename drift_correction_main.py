# drift_correction_main.py
import time
from collections import deque
import numpy as np
import json
from psp.Pv import Pv


class buffer_fill_timeout(Exception):
    """Raised when error buffer never fills within allowed iterations."""
    pass


class hutch_selection_changed(Exception):
    """Exception to catch changes to the hutch selected by the user."""
    pass


class drift_correction():
    """main class for drift correction"""
    def __init__(self):
        # Load hutch config file
        self.hutch_selector_pv = Pv('LAS:UNDS:FLOAT:40')
        self.hutch_selector = self.hutch_selector_pv.get(timeout=1.0)
        print(f"Initializing with hutch_selector: {self.hutch_selector}")

        if (self.hutch_selector == 1):  # qRIXS
            self.config = '/cds/group/laser/timing/lcls-drift-corr/qrixs_atm_fb.json'
            print("Using qRIXS configuration")
        else:  # cRIXS
            self.config = '/cds/group/laser/timing/lcls-drift-corr/crixs_atm_fb.json'
            print("Using cRIXS configuration")

        try:
            with open(self.config, 'r') as file:
                self.hutch_config = json.load(file)
                print("Configuration loaded successfully")
        except json.JSONDecodeError as e:  # Check json file
            print('Invalid JSON syntax: '+str(e))
            raise
        except Exception as e:
            print(f"Configuration loading failed: {e}")
            raise

        # Values from ATM timetool PV
        # only one should be uncommented at a time
        self.atm_err_pv = Pv(str(self.hutch_config['ttall_pv']))  # from json
        # self.atm_err_pv = Pv('RIX:TIMETOOL:TTALL')  # timetool PV
        # self.atm_err_pv = Pv('RIX:QRIX:ALV:01:TT:TTALL')  # Alvium TTALL
        # self.atm_err_pv = Pv('CRIX:TIMETOOL:TTALL')  # cRIXS timetool PV
        # self.atm_err_pv = Pv('QRIX:TIMETOOL:TTALL')  # qRIXS timetool PV

        # script control PVs
        self.heartbeat_pv = Pv('LAS:UNDS:FLOAT:41')
        self.on_off_pv = Pv('LAS:UNDS:FLOAT:67')  # enable/disable correction
        # ATM feedback hook to adjust laser timing
        self.atm_fb_pv = Pv('LAS:LHN:LLG2:02:PHASCTL:ATM_FBK_OFFSET')
        self.fb_direction_pv = Pv(str(self.hutch_config['fb_direction_pv']))
        self.fb_gain_pv = Pv(str(self.hutch_config['fb_gain_pv']))
        self.pos_offset_pv = Pv(str(self.hutch_config['pos_offset_pv']))  # fs

        # averaging PVs
        self.sample_size_pv = Pv(str(self.hutch_config['sample_size_pv']))
        self.avg_mode_pv = Pv(str(self.hutch_config['avg_mode_pv']))
        self.decay_factor_pv = Pv(str(self.hutch_config['decay_factor_pv']))

        # filter PVs
        self.ampl_min_pv = Pv(str(self.hutch_config['ampl_min_pv']))
        self.ampl_max_pv = Pv(str(self.hutch_config['ampl_max_pv']))
        self.curr_ampl_pv = Pv(str(self.hutch_config['curr_ampl_pv']))
        # average amplitude over sample period
        self.ampl_pv = Pv(str(self.hutch_config['ampl_pv']))
        self.fwhm_min_pv = Pv(str(self.hutch_config['fwhm_min_pv']))
        self.fwhm_max_pv = Pv(str(self.hutch_config['fwhm_max_pv']))
        self.curr_fwhm_pv = Pv(str(self.hutch_config['curr_fwhm_pv']))
        # average FWHM over sample period
        self.fwhm_pv = Pv(str(self.hutch_config['fwhm_pv']))
        self.pos_fs_min_pv = Pv(str(self.hutch_config['pos_fs_min_pv']))
        self.pos_fs_max_pv = Pv(str(self.hutch_config['pos_fs_max_pv']))
        self.curr_pos_fs_pv = Pv(str(self.hutch_config['curr_pos_fs_pv']))
        self.avg_pos_error = Pv(str(self.hutch_config['avg_pos_error']))
        # tracks correction to be applied
        self.correction_pv = Pv(str(self.hutch_config['correction_pv']))
        # TXT stage position
        self.txt_pv = Pv(str(self.hutch_config['txt_pv']))
        self.filter_state_pv = Pv(str(self.hutch_config['filter_state_pv']))

        # parameter and container initialization
        self.ampl_vals = deque()
        self.fwhm_vals = deque()
        self.error_vals = deque()
        self.max_fill_iterations = 500  # buffer for timeout

    def pull_filter_limits(self):
        """pulls current filtering thresholds from PVs"""
        self.ampl_min = self.ampl_min_pv.get(timeout=1.0)
        self.ampl_max = self.ampl_max_pv.get(timeout=1.0)
        self.fwhm_min = self.fwhm_min_pv.get(timeout=1.0)
        self.fwhm_max = self.fwhm_max_pv.get(timeout=1.0)
        self.pos_fs_min = self.pos_fs_min_pv.get(timeout=1.0)
        self.pos_fs_max = self.pos_fs_max_pv.get(timeout=1.0)

    def pull_atm_values(self):
        """pulls current atm values"""
        self.atm_err = self.atm_err_pv.get(timeout=60.0)
        # standard order
        self.atm_err_pos_ps = self.atm_err[1]  # pos ps
        self.atm_err_amp = self.atm_err[2]  # amplitude
        self.atm_err_fwhm = self.atm_err[5]  # FWHM
        # piranha special
        # self.atm_err_pos_ps = self.atm_err[2]  # pos ps
        # self.atm_err_amp = self.atm_err[0]  # amplitude
        # self.atm_err_fwhm = self.atm_err[3]  # FWHM
        # calculate offset adjusted position in fs
        # self.flt_pos_fs = (self.atm_err_pos_ps * 1000) - self.flt_pos_offset
        self.atm_err_pos_fs = (self.atm_err_pos_ps * 1000)

    def correct(self):
        """filters data and applies correction"""
        # Check for hutch value change
        self.hutch_selector_new = self.hutch_selector_pv.get(timeout=1.0)
        if (self.hutch_selector_new != self.hutch_selector):  # hutch change
            print("[DEBUG] Hutch change detected, raising exception")
            raise hutch_selection_changed
        # === Update values ===
        # get latest position offset
        self.flt_pos_offset = self.pos_offset_pv.get(timeout=1.0)
        self.pull_atm_values()
        # get current ATM FB hook value
        self.atm_fb = self.atm_fb_pv.get(timeout=60.0)
        self.pull_filter_limits()
        # get TXT position
        self.txt_prev = round(self.txt_pv.get(timeout=1.0), 1)
        self.bad_count = 0  # track how many times filter thresholds not met
        self.sample_size = self.sample_size_pv.get(timeout=1.0)
        # ============== loop for filling sample ======================
        # Initialize safety counter
        loop_counter = 0
        while (len(self.error_vals) < self.sample_size):
            loop_counter += 1
            if loop_counter > self.max_fill_iterations:
                raise buffer_fill_timeout
            # get current PV values
            self.pull_atm_values()
            self.curr_flt_pos_fs = self.atm_err_pos_fs - self.flt_pos_offset
            # check if filtering parameters have been updated
            if (self.bad_count > 9):
                self.pull_filter_limits()
                self.flt_pos_offset = self.pos_offset_pv.get(timeout=1.0)
                self.bad_count = 0
            # update tracking PVs
            self.curr_pos_fs_pv.put(value=self.atm_err_pos_fs, timeout=1.0)
            self.curr_ampl_pv.put(value=self.atm_err_amp, timeout=1.0)
            self.curr_fwhm_pv.put(value=self.atm_err_fwhm, timeout=1.0)
            # self.avg_pos_error.put(value=self.curr_flt_pos_fs, timeout=1.0)
            # ============= check and update filter state ==============
            self.filter_state = 0  # 0: passes all filter conditions
            if not (self.atm_err_amp > self.ampl_min):
                self.filter_state = 1  # amplitude too low
            if not (self.atm_err_amp < self.ampl_max):
                self.filter_state = 2  # amplitude too high
            if not (self.atm_err_fwhm > self.fwhm_min):
                self.filter_state = 3  # FWHM too low
            if not (self.atm_err_fwhm < self.fwhm_max):
                self.filter_state = 4  # FWHM too high
            if not (self.curr_flt_pos_fs > self.pos_fs_min):
                self.filter_state = 5  # position too low
            if not (self.curr_flt_pos_fs < self.pos_fs_max):
                self.filter_state = 6  # position too high
            # if not (self.flt_pos_fs != self.curr_flt_pos_fs):
            #     self.filter_state = 7  # position the same
            if not (round(self.txt_pv.get(timeout=1.0), 1) == self.txt_prev):
                self.filter_state = 8  # txt stage is moving
            # update filter state
            self.filter_state_pv.put(value=self.filter_state, timeout=1.0)
            if (self.filter_state == 0):
            # if True:  # DEBUG LINE - bypasses all filtering
                self.ampl = self.atm_err_amp  # unpack ampl filter parameter
                self.fwhm = self.atm_err_fwhm  # unpack fwhm filter parameter
                self.flt_pos_fs = self.curr_flt_pos_fs
                self.ampl_vals.append(self.ampl)
                self.fwhm_vals.append(self.fwhm)
                self.error_vals.append(self.flt_pos_fs)
                self.bad_count = 0
            else:
                self.bad_count += 1
            # update txt position for filtering
            self.txt_prev = round(self.txt_pv.get(timeout=1.0), 1)
        # ============= averaging ===============
        self.avg_mode = self.avg_mode_pv.get(timeout=1.0)
        # Check if we have any data to average
        if len(self.ampl_vals) == 0:
            return  # Skip this iteration if no valid data
        # Check for average mode
        # ONLY block averaging has been tested
        if (self.avg_mode == 1):  # block averaging
            self.avg_ampl = sum(self.ampl_vals) / len(self.ampl_vals)
            self.avg_fwhm = sum(self.fwhm_vals) / len(self.fwhm_vals)
            self.avg_error = sum(self.error_vals) / len(self.error_vals)
            # clear deques completely for next iteration
            self.ampl_vals.clear()
            self.fwhm_vals.clear()
            self.error_vals.clear()
        elif (self.avg_mode == 2):  # moving average
            self.avg_ampl = sum(self.ampl_vals) / len(self.ampl_vals)
            self.avg_fwhm = sum(self.fwhm_vals) / len(self.fwhm_vals)
            self.avg_error = sum(self.error_vals) / len(self.error_vals)
            # remove oldest element from deques
            self.ampl_vals.popleft()
            self.fwhm_vals.popleft()
            self.error_vals.popleft()
        else:  # decaying median filter
            # first, calculate moving average for amplitude and FWHM
            self.avg_ampl = sum(self.ampl_vals) / len(self.ampl_vals)
            self.avg_fwhm = sum(self.fwhm_vals) / len(self.fwhm_vals)
            # then calculate decaying median position
            self.decay_factor = self.decay_factor_pv.get(timeout=1.0)
            current_size = len(self.error_vals)  # Use actual deque size
            self.weights = [self.decay_factor ** (self.sample_size - i - 1) for i in range(current_size)]  # calculate weight of each element in deque
            self.weighted_values = [(self.error_vals[i], self.weights[i]) for i in range(current_size)]  # elements are paired with weights
            self.sorted_values = sorted(self.weighted_values, key=lambda x: x[0])  # sort element/weight pairs by element value
            self.cumulative_weights = np.cumsum([val[1] for val in self.sorted_values])  # calculate the cumulative weight
            self.total_weight = self.cumulative_weights[-1]
            self.target_weight = self.total_weight / 2
            # set to a default value in case loop doesn't execute
            self.avg_error = self.error_vals[-1] if len(self.error_vals) > 0 else 0
            # loop through until target weight reached
            for value, cum_weight in zip([val[0] for val in self.sorted_values], self.cumulative_weights):
                if cum_weight >= self.target_weight:
                    self.avg_error = value
                    break
            # remove oldest element from deques
            self.ampl_vals.popleft()
            self.fwhm_vals.popleft()
            self.error_vals.popleft()
        # ======= updates PVs & apply correction =================
        # update average value PVs of filter parameters and error
        self.ampl_pv.put(value=self.avg_ampl, timeout=1.0)
        self.fwhm_pv.put(value=self.avg_fwhm, timeout=1.0)
        # put average error to PV
        self.avg_pos_error.put(value=self.avg_error, timeout=1.0)
        # update control parameters and apply correction
        self.fb_direction = self.fb_direction_pv.get(timeout=1.0)
        self.fb_gain = self.fb_gain_pv.get(timeout=1.0)
        self.on_off = self.on_off_pv.get(timeout=1.0)
        # scale to ns, direction, and gain
        self.correction = (self.avg_error / 1000000) * self.fb_direction * self.fb_gain
        # correction to PV for logging
        self.correction_pv.put(value=(self.correction * 1000000), timeout=1.0)
        self.atm_fb = self.atm_fb + self.correction  # update ATM FB
        # only write if drift correction enabled and <1 ps
        if (self.on_off == 1) and ((abs(self.correction) < 0.001)):
            self.atm_fb_pv.put(value=self.atm_fb, timeout=1.0)
        else:
            pass


def run():
    # print(f"Hello world!")
    print(f"Drift correction script started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    correction = drift_correction()  # initialize
    heartbeat_counter = 0
    try:
        while True:
            try:
                # Update heartbeat
                heartbeat_counter += 1
                correction.heartbeat_pv.put(value=heartbeat_counter, timeout=1.0)
                correction.correct()
                time.sleep(0.1)
            except hutch_selection_changed:
                print("[INFO] Hutch selection changed.")
                correction = drift_correction()  # re-initialize
                correction.atm_fb_pv.put(value=0, timeout=1.0)
            except buffer_fill_timeout:
                print("[INFO] filter timeout.")
                # Short pause before retrying
                time.sleep(1.0)
            except Exception as e:
                print(f"[ERROR] Unexpected error: {e}")
                time.sleep(1.0)  # Prevent rapid error loops
    except KeyboardInterrupt:
        print("Script terminated by user.")


if __name__ == "__main__":
    run()
