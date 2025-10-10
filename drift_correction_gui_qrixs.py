# drift_correction_gui_qrixs.py
# EPICS import: suppresses epicscorelibs.path.pyepics warning
import epicscorelibs.path.pyepics
import epics.ca

# suppresses Qt WebEngine context warning
from qtpy.QtCore import Qt
from qtpy.QtWebEngineWidgets import QWebEngineView

from pydm import Display
from pydm.widgets import PyDMLabel, PyDMLineEdit, PyDMCheckbox
from qtpy.QtWidgets import QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout, QTabWidget, QWidget, QLabel, QPushButton, QMessageBox
from qtpy.QtCore import Qt

import subprocess
import psutil
import os
import time

class DriftCorrectionDisplay(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super(DriftCorrectionDisplay, self).__init__(parent=parent, args=args, macros=macros)

        self.setWindowTitle("qRIXS Drift Correction Control Panel")
        self.setMinimumSize(1000, 700)

        # Script management variables
        self.script_process = None
        self.script_path = "/cds/group/laser/timing/lcls-drift-corr/drift_correction_main.py"
        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        # Create tab widget
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        # Create tabs
        self.create_system_tab(tabs)
        self.create_filter_tab(tabs)
        # Call once immediately to set initial status
        self.update_script_status()

    def create_decimal_lineedit(self, channel, precision=3):
        """Helper to create a PyDMLineEdit with decimal display"""
        widget = PyDMLineEdit(init_channel=channel)
        widget.precision = precision
        widget.precisionFromPV = False
        widget.displayFormat = PyDMLineEdit.Decimal
        return widget

    def create_decimal_label(self, channel, precision=3):
        """Helper to create a PyDMLabel with decimal display"""
        widget = PyDMLabel(init_channel=channel)
        widget.precision = precision
        widget.precisionFromPV = False
        widget.displayFormat = PyDMLabel.Decimal
        return widget

    def create_integer_lineedit(self, channel):
        """Helper to create a PyDMLineEdit for integer values"""
        widget = PyDMLineEdit(init_channel=channel)
        widget.precision = 0
        widget.precisionFromPV = False
        return widget

    def create_integer_label(self, channel):
        """Helper to create a PyDMLabel for integer values"""
        widget = PyDMLabel(init_channel=channel)
        widget.precision = 0
        widget.precisionFromPV = False
        return widget

    def create_filter_tab(self, tabs):
        """Create filtering controls tab"""
        filter_widget = QWidget()
        filter_layout = QVBoxLayout(filter_widget)

        # Current values group
        current_group = QGroupBox("Current Values")
        current_layout = QGridLayout(current_group)
        # Current amplitude
        current_layout.addWidget(QLabel("Current Amplitude:"), 0, 0)
        curr_ampl_label = self.create_decimal_label("ca://LAS:UNDS:FLOAT:37", 3)
        current_layout .addWidget(curr_ampl_label, 0, 1)
        # Current FWHM
        current_layout.addWidget(QLabel("Current FWHM:"), 1, 0)
        curr_fwhm_label = self.create_decimal_label("ca://LAS:UNDS:FLOAT:33", 4)
        current_layout.addWidget(curr_fwhm_label, 1, 1)
        # Current position
        current_layout.addWidget(QLabel("Current Position (fs):"), 2, 0)
        curr_pos_label = self.create_decimal_label("ca://LAS:UNDS:FLOAT:29", 1)
        current_layout.addWidget(curr_pos_label, 2, 1)
        filter_layout.addWidget(current_group)

        # Amplitude filtering group
        ampl_group = QGroupBox("Amplitude Filtering")
        ampl_layout = QGridLayout(ampl_group)
        # Min amplitude
        ampl_layout.addWidget(QLabel("Min Amplitude:"), 0, 0)
        ampl_min_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:39", 3)
        ampl_layout.addWidget(ampl_min_edit, 0, 1)
        ampl_layout.addWidget(QLabel("Current:"), 0, 2)
        ampl_min_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:39", 3)
        ampl_min_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        ampl_layout.addWidget(ampl_min_readback, 0, 3)
        # Max amplitude  
        ampl_layout.addWidget(QLabel("Max Amplitude:"), 1, 0)
        ampl_max_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:38", 3)
        ampl_layout.addWidget(ampl_max_edit, 1, 1)
        ampl_layout.addWidget(QLabel("Current:"), 1, 2)
        ampl_max_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:38", 3)
        ampl_max_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        ampl_layout.addWidget(ampl_max_readback, 1, 3)
        filter_layout.addWidget(ampl_group)

        # FWHM filtering group
        fwhm_group = QGroupBox("FWHM Filtering")
        fwhm_layout = QGridLayout(fwhm_group)
        # Min FWHM
        fwhm_layout.addWidget(QLabel("Min FWHM:"), 0, 0)
        fwhm_min_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:35", 3)
        fwhm_layout.addWidget(fwhm_min_edit, 0, 1)
        fwhm_layout.addWidget(QLabel("Current:"), 0, 2)
        fwhm_min_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:35", 3)
        fwhm_min_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        fwhm_layout.addWidget(fwhm_min_readback, 0, 3)
        # Max FWHM
        fwhm_layout.addWidget(QLabel("Max FWHM:"), 1, 0)
        fwhm_max_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:34", 3)
        fwhm_layout.addWidget(fwhm_max_edit, 1, 1)
        fwhm_layout.addWidget(QLabel("Current:"), 1, 2)
        fwhm_max_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:34", 3)
        fwhm_max_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        fwhm_layout.addWidget(fwhm_max_readback, 1, 3)
        filter_layout.addWidget(fwhm_group)

        # Position filtering group
        pos_group = QGroupBox("Position Filtering (fs)")
        pos_layout = QGridLayout(pos_group)
        # Min position
        pos_layout.addWidget(QLabel("Min Position:"), 0, 0)
        pos_min_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:31", 1)
        pos_layout.addWidget(pos_min_edit, 0, 1)
        pos_layout.addWidget(QLabel("Current:"), 0, 2)
        pos_min_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:31", 1)
        pos_min_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        pos_layout.addWidget(pos_min_readback, 0, 3)
        # Max position
        pos_layout.addWidget(QLabel("Max Position:"), 1, 0)
        pos_max_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:30", 1)
        pos_layout.addWidget(pos_max_edit, 1, 1)
        pos_layout.addWidget(QLabel("Current:"), 1, 2)
        pos_max_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:30", 1)
        pos_max_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        pos_layout.addWidget(pos_max_readback, 1, 3)
        # Position offset
        pos_layout.addWidget(QLabel("Position Offset:"), 2, 0)
        pos_offset_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:27", 1)
        pos_layout.addWidget(pos_offset_edit, 2, 1)
        pos_layout.addWidget(QLabel("Current:"), 2, 2)
        pos_offset_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:27", 1)
        pos_offset_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        pos_layout.addWidget(pos_offset_readback, 2, 3)
        filter_layout.addWidget(pos_group)
        
        filter_layout.addStretch()

        tabs.addTab(filter_widget, "Filtering")

    def create_system_tab(self, tabs):
        """Create system controls tab"""
        system_widget = QWidget()
        system_layout = QVBoxLayout(system_widget)

        # Script Control Group
        script_group = QGroupBox("Script Control")
        script_layout = QGridLayout(script_group)
        # Script status display
        script_layout.addWidget(QLabel("Script Status:"), 0, 0)  # Static label is fine
        self.script_status_label = QLabel("Unknown")  # Dynamic label
        self.script_status_label.setMinimumSize(100, 30)
        self.script_status_label.setStyleSheet("padding: 5px; border: 1px solid #ccc; background-color: #f0f0f0;")
        script_layout.addWidget(self.script_status_label, 0, 1)
        # Process ID display 
        script_layout.addWidget(QLabel("Process ID:"), 0, 2)  # Static label is fine
        self.pid_label = QLabel("--")  # Dynamic label
        self.pid_label.setMinimumSize(60, 30)
        self.pid_label.setStyleSheet("padding: 5px; border: 1px solid #ccc; background-color: #f0f0f0;")
        script_layout.addWidget(self.pid_label, 0, 3)
        # Control buttons
        self.start_button = QPushButton("Start Script")
        self.start_button.clicked.connect(self.start_script)
        self.start_button.setStyleSheet("background-color: #90EE90; font-weight: bold;")
        script_layout.addWidget(self.start_button, 1, 0)
        self.stop_button = QPushButton("Stop Script")
        self.stop_button.clicked.connect(self.stop_script)
        self.stop_button.setStyleSheet("background-color: #FFB6C1; font-weight: bold;")
        script_layout.addWidget(self.stop_button, 1, 1)
        self.restart_button = QPushButton("Restart Script")
        self.restart_button.clicked.connect(self.restart_script)
        self.restart_button.setStyleSheet("background-color: #FFD700; font-weight: bold;")
        script_layout.addWidget(self.restart_button, 1, 2)
        self.check_button = QPushButton("Check Status")
        self.check_button.clicked.connect(self.manual_status_check)  # Use a wrapper method
        script_layout.addWidget(self.check_button, 1, 3)
        # Add Hutch selector label and line edit with readback after buttons (e.g. row 2 or next row)
        row = 2  # For example, put in row 2; adjust based on existing layout
        script_layout.addWidget(QLabel("Hutch Value (0=cRIXS, 1=qRIXS):"), row, 0)
        hutch_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:40", precision=0)
        script_layout.addWidget(hutch_edit, row, 1)
        script_layout.addWidget(QLabel("Current:"), row, 2)
        hutch_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:40", precision=0)
        hutch_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        script_layout.addWidget(hutch_readback, row, 3)
        system_layout.addWidget(script_group)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QGridLayout(status_group)
        # Filter state
        status_layout.addWidget(QLabel("Filter State:"), 0, 0)
        filter_state_label = self.create_integer_label("ca://LAS:UNDS:FLOAT:25")
        status_layout.addWidget(filter_state_label, 0, 1)
        # Heartbeat
        status_layout.addWidget(QLabel("Heartbeat:"), 1, 0)
        heartbeat_label = self.create_integer_label("ca://LAS:UNDS:FLOAT:41")
        status_layout.addWidget(heartbeat_label, 1, 1)
        system_layout.addWidget(status_group)

        # System control group
        control_group = QGroupBox("System Control")
        control_layout = QGridLayout(control_group)
        # On/Off checkbox
        control_layout.addWidget(QLabel("Drift Correction:"), 0, 0)
        onoff_checkbox = PyDMCheckbox(init_channel="ca://LAS:UNDS:FLOAT:67")
        control_layout.addWidget(onoff_checkbox, 0, 1)
        control_layout.addWidget(QLabel("Current:"), 0, 2)
        onoff_readback = self.create_integer_label("ca://LAS:UNDS:FLOAT:67")
        onoff_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        control_layout.addWidget(onoff_readback, 0, 3)
        system_layout.addWidget(control_group)

        # Feedback group
        fb_group = QGroupBox("Feedback Controls")
        fb_layout = QGridLayout(fb_group)
        # FB Direction
        fb_layout.addWidget(QLabel("FB Direction (-1 or 1):"), 0, 0)
        fb_dir_edit = self.create_integer_lineedit("ca://LAS:UNDS:FLOAT:22")
        fb_layout.addWidget(fb_dir_edit, 0, 1)
        fb_layout.addWidget(QLabel("Current:"), 0, 2)
        fb_dir_readback = self.create_integer_label("ca://LAS:UNDS:FLOAT:22")
        fb_dir_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        fb_layout.addWidget(fb_dir_readback, 0, 3)
        # FB Gain
        fb_layout.addWidget(QLabel("FB Gain:"), 1, 0)
        fb_gain_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:21", 4)
        fb_layout.addWidget(fb_gain_edit, 1, 1)
        fb_layout.addWidget(QLabel("Current:"), 1, 2)
        fb_gain_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:21", 4)
        fb_gain_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        fb_layout.addWidget(fb_gain_readback, 1, 3)
        system_layout.addWidget(fb_group)

        # Averaging group
        avg_group = QGroupBox("Averaging Controls")
        avg_layout = QGridLayout(avg_group)
        # Average mode
        avg_layout.addWidget(QLabel("Avg Mode (1=Block, 2=Moving, 3=Decay):"), 0, 0)
        avg_mode_edit = self.create_integer_lineedit("ca://LAS:UNDS:FLOAT:24")
        avg_layout.addWidget(avg_mode_edit, 0, 1)
        avg_layout.addWidget(QLabel("Current:"), 0, 2)
        avg_mode_readback = self.create_integer_label("ca://LAS:UNDS:FLOAT:24")
        avg_mode_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        avg_layout.addWidget(avg_mode_readback, 0, 3)
        # Sample size
        avg_layout.addWidget(QLabel("Sample Size:"), 1, 0)
        sample_size_edit = self.create_integer_lineedit("ca://LAS:UNDS:FLOAT:19")
        avg_layout.addWidget(sample_size_edit, 1, 1)
        avg_layout.addWidget(QLabel("Current:"), 1, 2)
        sample_size_readback = self.create_integer_label("ca://LAS:UNDS:FLOAT:19")
        sample_size_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        avg_layout.addWidget(sample_size_readback, 1, 3)
        # Decay factor
        avg_layout.addWidget(QLabel("Decay Factor:"), 2, 0)
        decay_edit = self.create_decimal_lineedit("ca://LAS:UNDS:FLOAT:23", 3)
        avg_layout.addWidget(decay_edit, 2, 1)
        avg_layout.addWidget(QLabel("Current:"), 2, 2)
        decay_readback = self.create_decimal_label("ca://LAS:UNDS:FLOAT:23", 3)
        decay_readback.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        avg_layout.addWidget(decay_readback, 2, 3)
        system_layout.addWidget(avg_group)
        
        system_layout.addStretch()

        tabs.addTab(system_widget, "Controls")

    def start_script(self):
        """Start the drift correction script"""
        print("=== START SCRIPT CALLED ===")
        try:
            # Force check
            running, pid = self.is_script_running()
            if running:
                self.show_message(f"Script is already running with PID: {pid}")
                return
            # Get absolute path to script
            script_full_path = os.path.abspath(self.script_path)
            if not os.path.exists(script_full_path):
                self.show_message(f"Script not found: {script_full_path}")
                return
            # Start the script with full path
            self.script_process = subprocess.Popen([
                'python', script_full_path
            ], cwd=os.path.dirname(script_full_path))
            self.show_message(f"Script started with PID: {self.script_process.pid}")
            self.update_script_status()
        except Exception as e:
            self.show_message(f"Failed to start script: {e}")
        time.sleep(2)  # Wait a moment
        self.update_script_status()

    def stop_script(self):
        """Stop the drift correction script"""
        print("=== STOP SCRIPT CALLED ===")
        try:
            killed_any = False
            # Find and kill all instances of the script
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
                try:
                    if (proc.info['cmdline'] and 
                        'drift_correction_main.py' in ' '.join(proc.info['cmdline']) and
                        proc.info['status'] not in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]):         
                        self.show_message(f"Stopping process PID: {proc.pid}")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                        killed_any = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            if not killed_any:
                self.show_message("No running script found to stop!")
            else:
                self.show_message("Script stopped successfully")
            self.script_process = None
            self.update_script_status()
        except Exception as e:
            self.show_message(f"Failed to stop script: {e}")
        time.sleep(2)  # Wait a moment
        self.update_script_status()

    def restart_script(self):
        """Restart the drift correction script"""
        self.stop_script()
        time.sleep(1)  # Wait a moment
        self.start_script()
        time.sleep(2)  # Wait a moment
        self.update_script_status()

    def manual_status_check(self):
        """Manual status check with extra debugging"""
        print("=== Manual Status Check ===")
        try:
            running, pid = self.is_script_running()
            print(f"Script running: {running}, PID: {pid}")
            # Try to update labels with debug
            if running:
                self.script_status_label.setText("RUNNING")
                self.script_status_label.setStyleSheet(
                    "padding: 5px; border: 1px solid #ccc; background-color: #90EE90; font-weight: bold;"
                )
                print("Status set to RUNNING")
            else:
                self.script_status_label.setText("STOPPED")
                self.script_status_label.setStyleSheet(
                    "padding: 5px; border: 1px solid #ccc; background-color: #FFB6C1; font-weight: bold;"
                )
                print("Status set to STOPPED")
            # Update PID label
            if pid:
                self.pid_label.setText(str(pid))
                print(f"PID set to {pid}")
            else:
                self.pid_label.setText("--")
                print("PID set to --")
            # Force repaint
            self.script_status_label.repaint()
            self.pid_label.repaint()
        except Exception as e:
            print(f"Error in manual_status_check: {e}")
            import traceback
            traceback.print_exc()

    def update_script_status(self):
        """Update the script status display"""
        try:
            running, pid = self.is_script_running()
            if running:
                self.script_status_label.setText("RUNNING")
                self.script_status_label.setStyleSheet(
                    "padding: 5px; border: 1px solid #ccc; background-color: #90EE90; font-weight: bold;"
                )
                self.pid_label.setText(str(pid))
            else:
                self.script_status_label.setText("STOPPED")
                self.script_status_label.setStyleSheet(
                    "padding: 5px; border: 1px solid #ccc; background-color: #FFB6C1; font-weight: bold;"
                )
                self.pid_label.setText("--")
        except Exception as e:
            print(f"Error in update_script_status: {e}")
            import traceback
            traceback.print_exc()

    def is_script_running(self):
        """Check if the drift correction script is currently running"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
                try:
                    # Skip zombie/dead processes
                    if proc.info['status'] in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
                        continue
                    # Check if cmdline exists and contains our script
                    if proc.info['cmdline']:
                        cmdline_str = ' '.join(proc.info['cmdline'])
                        if ('python' in cmdline_str.lower() and
                            'drift_correction_main.py' in cmdline_str and
                            proc.info['status'] in [psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING]):
                            print(f"[INFO] Found matching process: PID={proc.pid}, CMD={cmdline_str}")
                            return True, proc.pid
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            print("[INFO] No matching processes found")
            return False, None
        except Exception as e:
            print(f"[ERROR] Error in is_script_running: {e}")
            return False, None

    def show_message(self, message):
        """Show a status message (you could also use a status bar or popup)"""
        print(f"[GUI] {message}")  # For now, just print. You could add a status bar later

    def closeEvent(self, event):
        """Clean up when GUI is closed"""
        # Always check for running scripts
        running, pid = self.is_script_running()
        if running:
            reply = QMessageBox.question(self, 'Close Application', 
                                    f'Drift correction script is still running (PID: {pid}).\n\n'
                                    f'Do you want to stop it before closing the GUI?',
                                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                self.stop_script()
                event.accept()  # Close the GUI
            elif reply == QMessageBox.No:
                event.accept()  # Close GUI but leave script running
            else:  # Cancel
                event.ignore()  # Don't close the GUI
        else:
            event.accept()  # No script running, close normally

def main():
    import sys
    from pydm import PyDMApplication

    app = PyDMApplication(use_main_window=False)
    display = DriftCorrectionDisplay()
    display.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
