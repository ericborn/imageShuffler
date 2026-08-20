"""
Grid widget containing multiple image displays with crossfade transitions
"""
from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtSignal
from PyQt6 import sip
from image_display import ImageDisplay
from image_utils import get_next_images, ROWS, COLS, IMAGES_PER_VIEW

class ImageGrid(QWidget):
    """Widget containing the grid of images with crossfade transitions"""
    
    row_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.widgets = []
        self.current_row = 0
        self.transitioning = False
        self.animation_group = None
        self.transition_duration = 20000 # Default 20 seconds
        self.setup_ui()
        
    def setup_ui(self):
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.initialize_with_images()
        
    def initialize_with_images(self):
        images = get_next_images(IMAGES_PER_VIEW)
        
        if not images:
            for row in range(ROWS):
                for col in range(COLS):
                    placeholder = QLabel("No Images Found")
                    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder.setStyleSheet("color: #666; background-color: #1a1a1a; border-radius: 8px; font-size: 16px;")
                    placeholder.setMinimumSize(500, 500)
                    placeholder.setMaximumSize(500, 600)
                    self.grid_layout.addWidget(placeholder, row, col)
            return
        
        for row in range(ROWS):
            for col in range(COLS):
                idx = row * COLS + col
                if idx < len(images):
                    image_widget = ImageDisplay(images[idx], self, self.replace_widget, is_fading=False)
                    image_widget.get_opacity_effect().setOpacity(1.0)
                    self.grid_layout.addWidget(image_widget, row, col)
                else:
                    placeholder = QLabel("No Image")
                    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder.setStyleSheet("color: #666; background-color: #1a1a1a; border-radius: 8px;")
                    placeholder.setMinimumSize(500, 500)
                    placeholder.setMaximumSize(500, 600)
                    self.grid_layout.addWidget(placeholder, row, col)
    
    def set_transition_duration(self, duration):
        self.transition_duration = duration
    
    def load_images_for_row(self, row):
        if self.transitioning:
            return
        
        self.transitioning = True
        self.current_row = row
        
        images = get_next_images(COLS)
        
        # Get current widgets in this row
        old_widgets = []
        for col in range(COLS):
            item = self.grid_layout.itemAtPosition(row, col)
            if item and item.widget() and isinstance(item.widget(), ImageDisplay):
                old_widgets.append(item.widget())
        
        # Create new widgets
        new_widgets = []
        for col, img_path in enumerate(images):
            new_widget = ImageDisplay(img_path, self, self.replace_widget, is_fading=True)
            new_widget.get_opacity_effect().setOpacity(0.0)
            new_widget.setStyleSheet("""
                QFrame#imageDisplay {
                    background-color: transparent;
                    border: 2px solid transparent;
                    border-radius: 8px;
                }
            """)
            self.grid_layout.addWidget(new_widget, row, col)
            new_widgets.append(new_widget)
        
        # Create crossfade animation
        self.animation_group = QParallelAnimationGroup()
        
        for old_widget in old_widgets:
            fade_out = QPropertyAnimation(old_widget.get_opacity_effect(), b"opacity")
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.setDuration(self.transition_duration)
            fade_out.setEasingCurve(QEasingCurve.Type.InSine)
            self.animation_group.addAnimation(fade_out)
        
        for new_widget in new_widgets:
            fade_in = QPropertyAnimation(new_widget.get_opacity_effect(), b"opacity")
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setDuration(self.transition_duration)
            fade_in.setEasingCurve(QEasingCurve.Type.InSine)
            fade_in.finished.connect(lambda w=new_widget: w.set_fading(False))
            self.animation_group.addAnimation(fade_in)
        
        self.animation_group.finished.connect(
            lambda old_widgets=old_widgets, row=row: self.on_animation_finished(old_widgets, row)
        )
        self.animation_group.start()
    
    def on_animation_finished(self, old_widgets, row):
        self.finish_transition(old_widgets.copy(), row)
    
    def finish_transition(self, old_widgets, row):
        for old_widget in old_widgets:
            if old_widget is None or sip.isdeleted(old_widget):
                continue
            try:
                if self.grid_layout.indexOf(old_widget) != -1:
                    self.grid_layout.removeWidget(old_widget)
                    old_widget.deleteLater()
            except (RuntimeError, AttributeError):
                continue
        
        self.transitioning = False
        self.row_changed.emit(row)
        
        if hasattr(self.parent(), 'row_transition_timer'):
            self.parent().row_transition_timer.start()
    
    def start_row_sequence(self):
        if not self.transitioning:
            self.load_images_for_row(0)
    
    def next_row(self):
        if self.transitioning:
            return
        next_row = (self.current_row + 1) % ROWS
        self.load_images_for_row(next_row)
    
    def replace_widget(self, old_widget):
        for row in range(ROWS):
            for col in range(COLS):
                item = self.grid_layout.itemAtPosition(row, col)
                if item and item.widget() == old_widget:
                    new_images = get_next_images(1)
                    if new_images:
                        new_widget = ImageDisplay(new_images[0], self, self.replace_widget, is_fading=False)
                        self.grid_layout.replaceWidget(old_widget, new_widget)
                        old_widget.deleteLater()
                        return
                    else:
                        placeholder = QLabel("No More Images")
                        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        placeholder.setStyleSheet("color: #666; background-color: #1a1a1a; border-radius: 8px;")
                        placeholder.setMinimumSize(500, 500)
                        placeholder.setMaximumSize(500, 600)
                        self.grid_layout.replaceWidget(old_widget, placeholder)
                        old_widget.deleteLater()
                        return