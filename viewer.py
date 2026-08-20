"""
Main photo viewer window
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSlider, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from image_grid import ImageGrid, ROWS
from hotkeys import QtKeyBinder
from database import init_db
from image_utils import refresh_list

class PhotoViewer(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Viewer - Crossfade Mode")
        self.setMinimumSize(5, 5)
        self.is_shrunk = False
        
        # Key binder
        self.key_binder = QtKeyBinder(win_id=None)
        self.key_binder.register_hotkey('Alt+Z', self.toggle_window_size)
        
        # Transition settings
        self.transition_duration = 3000
        self.row_transition_duration = 300000
        self.initial_delay = 300000
        
        # Pause state
        self.is_paused = False
        self.pause_state_sticky = False
        self.remaining_time = 0
        
        # Initialize database and images
        init_db()
        refresh_list()
        
        # Setup UI
        self.setup_ui()

        # Timers
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.sticky_timer = QTimer()
        self.sticky_timer.setSingleShot(True)
        self.sticky_timer.timeout.connect(self.clear_sticky_state)
        self.row_transition_timer = QTimer()
        self.row_transition_timer.setSingleShot(True)
        self.row_transition_timer.timeout.connect(self.image_grid.next_row)
        
        # Start slideshow
        QTimer.singleShot(self.initial_delay, self.start_slideshow)

    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Control bar
        control_bar = QWidget()
        control_bar.setFixedHeight(100)
        control_bar.setStyleSheet("background-color: #263238; border-bottom: 1px solid #333;")
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(20, 0, 20, 0)
        control_layout.setSpacing(15)
        
        # Status label
        self.status_label = QLabel("🔄 Crossfading - Row 1/3")
        self.status_label.setStyleSheet("color: #ccc; font-size: 14px; font-family: Arial, sans-serif;")
        control_layout.addWidget(self.status_label)
        
        # Countdown label
        self.countdown_label = QLabel("⏱ Next transition in: 300s")
        self.countdown_label.setStyleSheet("color: #FFB74D; font-size: 14px; font-family: Arial, sans-serif; font-weight: bold;")
        control_layout.addWidget(self.countdown_label)
        
        control_layout.addStretch()
        
        # Sliders container
        sliders_container = QWidget()
        sliders_layout = QVBoxLayout(sliders_container)
        sliders_layout.setContentsMargins(0, 0, 0, 0)
        sliders_layout.setSpacing(5)
        
        # Fade duration slider
        fade_container = QWidget()
        fade_layout = QHBoxLayout(fade_container)
        fade_layout.setContentsMargins(0, 0, 0, 0)
        fade_layout.setSpacing(10)
        
        fade_label = QLabel("Fade Duration:")
        fade_label.setStyleSheet("color: #ccc; font-size: 13px;")
        fade_layout.addWidget(fade_label)
        
        self.fade_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_slider.setMinimum(1)
        self.fade_slider.setMaximum(10)
        self.fade_slider.setValue(3)
        self.fade_slider.setFixedWidth(150)
        self.fade_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #505059;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 15px;
                height: 15px;
                border-radius: 8px;
                background: #9DCFE8;
                margin: -6px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #b5dff5;
            }
        """)
        self.fade_slider.valueChanged.connect(self.update_fade_duration)
        fade_layout.addWidget(self.fade_slider)
        
        self.fade_value_label = QLabel("3s")
        self.fade_value_label.setStyleSheet("color: #ccc; font-size: 13px; min-width: 30px;")
        fade_layout.addWidget(self.fade_value_label)
        
        sliders_layout.addWidget(fade_container)
        
        # Row interval slider
        interval_container = QWidget()
        interval_layout = QHBoxLayout(interval_container)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(10)
        
        interval_label = QLabel("Row Interval:")
        interval_label.setStyleSheet("color: #ccc; font-size: 13px;")
        interval_layout.addWidget(interval_label)
        
        self.interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.interval_slider.setMinimum(1)
        self.interval_slider.setMaximum(20)
        self.interval_slider.setValue(20)
        self.interval_slider.setFixedWidth(150)
        self.interval_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.interval_slider.setTickInterval(1)
        self.interval_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #505059;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 15px;
                height: 15px;
                border-radius: 8px;
                background: #FFB74D;
                margin: -6px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #FFA726;
            }
        """)
        self.interval_slider.valueChanged.connect(self.update_row_interval)
        interval_layout.addWidget(self.interval_slider)
        
        self.interval_value_label = QLabel("300s")
        self.interval_value_label.setStyleSheet("color: #ccc; font-size: 13px; min-width: 30px;")
        interval_layout.addWidget(self.interval_value_label)
        
        sliders_layout.addWidget(interval_container)
        
        control_layout.addWidget(sliders_container)
        
        # Pause button
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #404049;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505059;
            }
        """)
        self.pause_btn.clicked.connect(self.toggle_pause)
        control_layout.addWidget(self.pause_btn)
        
        # Skip button
        skip_btn = QPushButton("⏭ Skip Row")
        skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #404049;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505059;
            }
        """)
        skip_btn.clicked.connect(self.skip_row)
        control_layout.addWidget(skip_btn)
        
        main_layout.addWidget(control_bar)
        
        # Image grid
        self.image_grid = ImageGrid()
        self.image_grid.set_transition_duration(self.transition_duration)
        self.image_grid.row_changed.connect(self.on_row_changed)
        main_layout.addWidget(self.image_grid)

    def start_slideshow(self):
        self.image_grid.start_row_sequence()

    def update_fade_duration(self, value):
        self.transition_duration = value * 1000
        self.fade_value_label.setText(f"{value}s")
        self.image_grid.set_transition_duration(self.transition_duration)

    def update_row_interval(self, value):
        seconds = value * 15
        self.row_transition_duration = seconds * 1000
        self.interval_value_label.setText(f"{seconds}s")
        
        if self.row_transition_timer.isActive():
            self.row_transition_timer.stop()
            if not self.is_paused:
                self.row_transition_timer.start(self.row_transition_duration)
                self.remaining_time = self.row_transition_duration
                self.countdown_timer.start(1000)
        
        if self.is_paused:
            self.remaining_time = self.row_transition_duration
            self.update_countdown_display()

    def update_countdown(self):
        if self.is_paused:
            self.update_countdown_display()
            return
        
        if self.row_transition_timer.isActive():
            self.remaining_time = self.row_transition_timer.remainingTime()
            if self.remaining_time <= 0:
                self.countdown_label.setText("⏱ Transitioning...")
            else:
                seconds = self.remaining_time // 1000
                minutes = seconds // 60
                remaining_seconds = seconds % 60
                if minutes > 0:
                    self.countdown_label.setText(f"⏱ Next transition in: {minutes}m {remaining_seconds}s")
                else:
                    self.countdown_label.setText(f"⏱ Next transition in: {seconds}s")
        else:
            self.countdown_label.setText("⏱ Waiting for transition...")
    
    def update_countdown_display(self):
        seconds = self.remaining_time // 1000
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        if minutes > 0:
            self.countdown_label.setText(f"⏱ Next transition in: {minutes}m {remaining_seconds}s")
        else:
            self.countdown_label.setText(f"⏱ Next transition in: {seconds}s")
    
    def on_row_changed(self, row):
        self.status_label.setText(f"🔄 Crossfading - Row {row + 1}/{ROWS}")
        if not self.is_paused:
            self.row_transition_timer.start(self.row_transition_duration)
            self.remaining_time = self.row_transition_duration
            self.countdown_timer.start(1000)

    @pyqtSlot()
    def toggle_window_size(self):
        if not self.is_shrunk:
            self.showMinimized()
            self.is_shrunk = True
            self.enable_pause()
        else:
            self.showMaximized()
            self.is_shrunk = False
            self.disable_pause()

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self.pause_btn.setText("▶ Resume")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a6a4a;
                    color: #ccc;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #5a7a5a;
                }
            """)
            if self.row_transition_timer.isActive():
                self.remaining_time = self.row_transition_timer.remainingTime()
                self.row_transition_timer.stop()
            self.countdown_timer.stop()
            self.status_label.setText("⏸ Paused")
            self.update_countdown_display()
        else:
            self.pause_btn.setText("⏸ Pause")
            self.pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #404049;
                    color: #ccc;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #505059;
                }
            """)
            self.status_label.setText("▶ Resumed")
            if not self.image_grid.transitioning:
                if self.remaining_time > 0:
                    self.row_transition_timer.start(self.remaining_time)
                    self.countdown_timer.start(1000)
                else:
                    self.row_transition_timer.start(self.row_transition_duration)
                    self.remaining_time = self.row_transition_duration
                    self.countdown_timer.start(1000)
            else:
                self.status_label.setText("▶ Resumed - waiting for current transition...")
    
    def enable_pause(self):
        self.is_paused = True
        self.pause_btn.setText("▶ Resume")
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6a4a;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a7a5a;
            }
        """)
        if self.row_transition_timer.isActive():
            self.remaining_time = self.row_transition_timer.remainingTime()
            self.row_transition_timer.stop()
        self.countdown_timer.stop()
        self.status_label.setText("⏸ Paused")
        self.update_countdown_display()
        self.pause_state_sticky = True
        self.sticky_timer.start(3000)

    def disable_pause(self):
        self.is_paused = False
        self.pause_btn.setText("⏸ Pause")
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #404049;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505059;
            }
        """)
        self.status_label.setText("▶ Resumed")
        if not self.image_grid.transitioning:
            if self.remaining_time > 0:
                self.row_transition_timer.start(self.remaining_time)
                self.countdown_timer.start(1000)
            else:
                self.row_transition_timer.start(self.row_transition_duration)
                self.remaining_time = self.row_transition_duration
                self.countdown_timer.start(1000)
        else:
            self.status_label.setText("▶ Resumed - waiting for current transition...")
        self.pause_state_sticky = True
        self.sticky_timer.start(3000)

    def clear_sticky_state(self):
        self.pause_state_sticky = False
        if not self.is_paused:
            self.status_label.setText(f"🔄 Crossfading - Row {self.image_grid.current_row + 1}/{ROWS}")

    def skip_row(self):
        if not self.is_paused:
            self.row_transition_timer.stop()
            if not self.image_grid.transitioning:
                self.image_grid.next_row()

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                self.is_shrunk = True
                self.enable_pause()
            elif self.isMaximized() or self.isFullScreen():
                self.is_shrunk = False
                self.disable_pause()
        super().changeEvent(event)

    def closeEvent(self, event):
        self.row_transition_timer.stop()
        self.countdown_timer.stop()
        if hasattr(self, 'key_binder'):
            self.key_binder.unregister_hotkey('Alt+Z')
        event.accept()

    def pause_slideshow(self):
        """Pause the slideshow for fullscreen viewing"""
        if not self.is_paused:
            self.toggle_pause()

    def resume_after_fullscreen(self):
        """Resume the slideshow after fullscreen viewer closes"""
        if self.is_paused:
            self.toggle_pause()
        # Ensure timer is running
        if not self.row_transition_timer.isActive() and not self.image_grid.transitioning:
            self.row_transition_timer.start(self.row_transition_duration)
            self.remaining_time = self.row_transition_duration
            self.countdown_timer.start(1000)