"""
PyQt6 Desktop Photo Viewer with Crossfade Transitions
Converted from Flask web application to desktop app
"""

import os
import glob
import random
import sqlite3
import sys
from datetime import datetime
from send2trash import send2trash
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QScrollArea, QPushButton, QLabel, QSlider, QFrame,
    QMessageBox, QCheckBox, QSizePolicy, QStackedWidget,
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect,
    pyqtSignal, QThread, QRectF, QPoint, QSize, QParallelAnimationGroup, 
    QMetaObject, pyqtSlot, QAbstractNativeEventFilter, QAbstractEventDispatcher
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QFont,
    QImage, QIcon, QAction, QKeySequence, QPalette
)
from PyQt6 import sip

# Import pyqtkeybind
from pyqtkeybind import keybinder

# Get the directory where the script is located
path = os.path.dirname(os.path.realpath(__file__))
DB_PATH = os.path.join(path, 'favorites.db')

# Global variables
all_images = []
current_index = 0
BATCH_SIZE = 30  # Load more images at once
ROWS = 3
COLS = 2
IMAGES_PER_VIEW = ROWS * COLS  # 6 images

def init_db():
    """Initialize the database if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            image_id TEXT PRIMARY KEY,
            filename TEXT,
            favorited INTEGER DEFAULT 0,
            favorited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            times_displayed INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def normalize_path(file_path):
    """Convert any path to use forward slashes"""
    return file_path.replace('\\', '/')

def refresh_list():
    """Refresh the master list of all images"""
    global all_images, current_index
    
    # Find all image files recursively in static folder
    images_path = os.path.join(path, 'static')
    image_files = []
    
    if os.path.exists(images_path):
        # Walk through Images directory
        for root, dirs, files in os.walk(images_path):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                    if file == 'heart.png' or file == 'trash.png':
                        continue
                    full_path = os.path.join(root, file)
                    # Get relative path from Images directory
                    rel_path = os.path.relpath(full_path, images_path)
                    image_files.append(normalize_path(rel_path))
    
    if not image_files:
        return []
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Separate images into never seen and seen
    never_seen = []
    seen = []

    for img_path in image_files:
        image_id = os.path.basename(img_path)
        cursor.execute('SELECT times_displayed FROM favorites WHERE image_id = ?', (image_id,))
        result = cursor.fetchone()
        
        if result is None or result[0] == 0:
            never_seen.append(img_path)
        else:
            seen.append(img_path)
    
    conn.close()
    
    # Shuffle and combine
    random.shuffle(never_seen)
    random.shuffle(seen)
    
    all_images = never_seen + seen
    current_index = 0
    
    return all_images

def mark_as_seen(image_path):
    """Mark an image as seen in the database by incrementing times_displayed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_id = os.path.basename(image_path)
    abs_path = os.path.join(path, 'static', image_path)
    
    cursor.execute('SELECT times_displayed FROM favorites WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    
    if result:
        new_count = result[0] + 1
        cursor.execute(
            'UPDATE favorites SET times_displayed = ? WHERE image_id = ?',
            (new_count, image_id)
        )
    else:
        cursor.execute(
            'INSERT INTO favorites (image_id, filename, times_displayed) VALUES (?, ?, 1)',
            (image_id, normalize_path(abs_path))
        )
    
    conn.commit()
    conn.close()

def get_next_images(count=None):
    """Get next batch of images for display"""
    global all_images, current_index
    
    if count is None:
        count = IMAGES_PER_VIEW
    
    if not all_images:
        refresh_list()
        return []
    
    if current_index >= len(all_images):
        refresh_list()
        current_index = 0
    
    end_index = min(current_index + count, len(all_images))
    selected = all_images[current_index:end_index]
    current_index = end_index
    
    # If we don't have enough images, wrap around
    if len(selected) < count and len(all_images) > 0:
        # Get remaining images from the beginning
        remaining = count - len(selected)
        end_index = min(remaining, len(all_images))
        selected.extend(all_images[0:end_index])
        current_index = end_index
    
    return selected

def toggle_favorite(image_path):
    """Toggle favorite status for an image"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_id = os.path.basename(image_path)
    abs_path = os.path.join(path, 'static', image_path)
    
    cursor.execute('SELECT favorited FROM favorites WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    
    if result:
        new_status = 0 if result[0] == 1 else 1
        cursor.execute(
            'UPDATE favorites SET favorited = ?, favorited_at = CURRENT_TIMESTAMP WHERE image_id = ?',
            (new_status, image_id)
        )
    else:
        new_status = 1
        cursor.execute(
            'INSERT INTO favorites (image_id, filename, favorited) VALUES (?, ?, ?)',
            (image_id, normalize_path(abs_path), new_status)
        )
    
    conn.commit()
    conn.close()
    return bool(new_status)

def is_favorited(image_path):
    """Check if an image is favorited"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = os.path.basename(image_path)
    
    cursor.execute('SELECT favorited FROM favorites WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    conn.close()
    
    return bool(result[0]) if result else False

def delete_image(image_path):
    """Delete an image from disk and remove from favorites"""
    abs_path = os.path.join(path, 'static', image_path)
    abs_path = os.path.normpath(abs_path)
    
    if os.path.exists(abs_path):
        send2trash(abs_path)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = os.path.basename(image_path)
    cursor.execute('DELETE FROM favorites WHERE image_id = ?', (image_id,))
    conn.commit()
    conn.close()
    
    return True

class ImageDisplay(QFrame):
    """Widget for displaying a single image with overlay buttons"""
    
    def __init__(self, image_path, parent=None, delete_callback=None, is_fading=False):
        super().__init__(parent)
        self.image_path = image_path
        self.is_favorited = is_favorited(image_path)
        self.delete_callback = delete_callback
        self.is_fading = is_fading  # Track if this image is currently fading in
        self.setup_ui()
        
    def setup_ui(self):
        self.setObjectName("imageDisplay")
        self.setStyleSheet("""
            QFrame#imageDisplay {
                background-color: #1a1a1a;
                border: 2px solid #333;
                border-radius: 8px;
            }
            QFrame#imageDisplay:hover {
                border: 2px solid #666;
            }
        """)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Image label with center alignment and fixed size
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            background-color: transparent;
            border: none;
        """)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed
        )
        
        # Add opacity effect for crossfade
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(1.0)
        self.image_label.setGraphicsEffect(self.opacity_effect)
        
        layout.addWidget(self.image_label)
        
        # Overlay container
        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0);
                border-radius: 8px;
            }
        """)
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setVisible(False)
        
        # Overlay layout - use QVBoxLayout to position at bottom
        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(15, 10, 15, 15)
        overlay_layout.setSpacing(5)
        
        # Add stretch to push buttons to bottom
        overlay_layout.addStretch()
        
        # Bottom container for heart and trash
        bottom_container = QHBoxLayout()
        bottom_container.setContentsMargins(0, 0, 0, 0)
        bottom_container.setSpacing(5)
        
        # Heart button - left side
        self.heart_btn = QPushButton("❤️")
        self.heart_btn.setFixedSize(35, 35)
        self.heart_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.8);
                border: none;
                border-radius: 17px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 1);
            }
            QPushButton[favorited="true"] {
                background-color: rgba(255, 50, 50, 0.9);
            }
        """)
        self.heart_btn.clicked.connect(self.toggle_favorite)
        if self.is_favorited:
            self.heart_btn.setProperty("favorited", True)
            self.heart_btn.style().unpolish(self.heart_btn)
            self.heart_btn.style().polish(self.heart_btn)
        
        bottom_container.addWidget(self.heart_btn)
        
        # Add stretch between heart and trash
        bottom_container.addStretch()
        
        # Trash button - right side
        self.trash_btn = QPushButton("🗑️")
        self.trash_btn.setFixedSize(35, 35)
        self.trash_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.8);
                border: none;
                border-radius: 17px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 1);
            }
        """)
        self.trash_btn.clicked.connect(self.delete_image)
        bottom_container.addWidget(self.trash_btn)
        
        overlay_layout.addLayout(bottom_container)
        
        # Load image
        self.load_image()
        
        # Timer for hover delay
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.show_overlay)
        
    def resizeEvent(self, event):
        """Handle resize to update overlay position"""
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(0, 0, self.width(), self.height())
        
    def load_image(self):
        """Load and display the image with proper sizing"""
        abs_path = os.path.join(path, 'static', self.image_path)
        if os.path.exists(abs_path):
            pixmap = QPixmap(abs_path)
            if not pixmap.isNull():
                # Get image dimensions
                img_width = pixmap.width()
                img_height = pixmap.height()
                
                # Determine if image is tall (1.25x taller than wide) or square
                aspect_ratio = img_height / img_width
                
                # Set target dimensions
                if aspect_ratio >= 1.2:  # Tall image (1.25x or more)
                    target_width = 500
                    target_height = 600
                else:  # Square or landscape image
                    target_width = 500
                    target_height = 500
                
                # Scale to fit target dimensions while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    target_width, target_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Set the widget's size to accommodate padding
                if aspect_ratio >= 1.2:
                    self.setMaximumSize(500, 600)
                    self.setMinimumSize(500, 600)
                else:
                    self.setMaximumSize(500, 500)
                    self.setMinimumSize(500, 500)
                
                # Create a new pixmap with the exact target dimensions and center the image
                final_pixmap = QPixmap(target_width, target_height)
                final_pixmap.fill(Qt.GlobalColor.transparent)
                
                # Calculate position to center the scaled image
                x = (target_width - scaled_pixmap.width()) // 2
                y = (target_height - scaled_pixmap.height()) // 2
                
                # Paint the scaled image onto the final pixmap
                painter = QPainter(final_pixmap)
                painter.drawPixmap(x, y, scaled_pixmap)
                painter.end()
                
                self.image_label.setPixmap(final_pixmap)
                return
        
        # Show placeholder if image can't be loaded
        self.image_label.setText("📷\nNo Image")
        self.image_label.setStyleSheet("color: #666; font-size: 20px;")
        
    def get_opacity_effect(self):
        """Return the opacity effect for animation"""
        return self.opacity_effect
        
    def enterEvent(self, event):
        """Mouse enters widget"""
        # Only show overlay if the image is fully visible (not fading)
        if not self.is_fading:
            self.hover_timer.start(200)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Mouse leaves widget"""
        self.hover_timer.stop()
        self.overlay.setVisible(False)
        super().leaveEvent(event)
        
    def show_overlay(self):
        """Show overlay after hover delay"""
        self.overlay.setVisible(True)
        
    def set_fading(self, fading):
        """Set whether this image is currently fading in"""
        self.is_fading = fading
        # If fading, hide overlay
        if fading:
            self.overlay.setVisible(False)
            self.hover_timer.stop()
        
    def toggle_favorite(self):
        """Toggle favorite status"""
        self.is_favorited = toggle_favorite(self.image_path)
        self.heart_btn.setProperty("favorited", self.is_favorited)
        self.heart_btn.style().unpolish(self.heart_btn)
        self.heart_btn.style().polish(self.heart_btn)

    def delete_image(self):
        """Delete the image"""
        reply = QMessageBox.question(
            self, 'Delete Image',
            'Are you sure you want to delete this image?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if delete_image(self.image_path):
                # Call the callback to replace this widget
                if self.delete_callback:
                    self.delete_callback(self)
                else:
                    # Fallback: just remove from grid
                    parent_grid = self.parent()
                    if parent_grid and hasattr(parent_grid, 'remove_widget'):
                        parent_grid.remove_widget(self)
                    self.deleteLater()

class ImageGrid(QWidget):
    """Widget containing the grid of images with crossfade transitions"""
    
    row_changed = pyqtSignal(int)  # Emitted when a row changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self.widgets = []
        self.current_row = 0
        self.transitioning = False
        self.animation_group = None
        self.transition_duration = 20000  # Default 20 seconds
        self.setup_ui()
        
    def setup_ui(self):
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        
        # Initialize with actual images instead of placeholders
        self.initialize_with_images()
        
    def initialize_with_images(self):
        """Initialize grid with actual images"""
        # Get first batch of images
        images = get_next_images(IMAGES_PER_VIEW)
        
        # If no images, show placeholders
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
        
        # Mark images as seen
        for img in images:
            mark_as_seen(img)
        
        # Create ImageDisplay widgets for each image
        for row in range(ROWS):
            for col in range(COLS):
                idx = row * COLS + col
                if idx < len(images):
                    # Pass the replace_widget method as callback
                    image_widget = ImageDisplay(images[idx], self, self.replace_widget, is_fading=False)
                    # Set initial opacity to 1.0 (fully visible)
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
        """Set the transition duration in milliseconds"""
        self.transition_duration = duration
    
    def load_images_for_row(self, row):
        """Load images for a specific row with crossfade"""
        if self.transitioning:
            return
        
        self.transitioning = True
        self.current_row = row
        
        # Get images for this row
        images = get_next_images(COLS)
        
        # Mark images as seen (increment times_displayed)
        for img in images:
            mark_as_seen(img)
        
        # Get current widgets in this row
        old_widgets = []
        for col in range(COLS):
            item = self.grid_layout.itemAtPosition(row, col)
            if item and item.widget() and isinstance(item.widget(), ImageDisplay):
                old_widgets.append(item.widget())
        
        # Create new widgets with starting opacity 0
        new_widgets = []
        for col, img_path in enumerate(images):
            # Pass the replace_widget method as callback
            # Mark as fading in
            new_widget = ImageDisplay(img_path, self, self.replace_widget, is_fading=True)
            # Set initial opacity to 0
            new_widget.get_opacity_effect().setOpacity(0.0)
            # CRITICAL: Make the widget background transparent so old image shows through
            new_widget.setStyleSheet("""
                QFrame#imageDisplay {
                    background-color: transparent;
                    border: 2px solid transparent;
                    border-radius: 8px;
                }
            """)
            self.grid_layout.addWidget(new_widget, row, col)
            new_widgets.append(new_widget)
        
        # Create crossfade animation - FADE OLD OUT AND NEW IN SIMULTANEOUSLY
        self.animation_group = QParallelAnimationGroup()
        
        # Fade out old widgets - animate the opacity effect
        for old_widget in old_widgets:
            fade_out = QPropertyAnimation(old_widget.get_opacity_effect(), b"opacity")
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.setDuration(self.transition_duration)
            fade_out.setEasingCurve(QEasingCurve.Type.InSine)
            self.animation_group.addAnimation(fade_out)
        
        # Fade in new widgets - animate the opacity effect
        for new_widget in new_widgets:
            fade_in = QPropertyAnimation(new_widget.get_opacity_effect(), b"opacity")
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setDuration(self.transition_duration)
            fade_in.setEasingCurve(QEasingCurve.Type.InSine)
            # When fade in completes, mark widget as no longer fading
            fade_in.finished.connect(lambda w=new_widget: w.set_fading(False))
            self.animation_group.addAnimation(fade_in)
        
        # Clean up old widgets when animation completes
        self.animation_group.finished.connect(
            lambda old_widgets=old_widgets, row=row: self.on_animation_finished(old_widgets, row)
        )
        self.animation_group.start()
    
    def on_transition_complete(self, old_widgets, row):
        """Handle completion of transition"""
        for old_widget in old_widgets:
            # Check if widget is None or has been deleted
            if old_widget is None or sip.isdeleted(old_widget):
                continue
                
            try:
                # Check if it's still in the layout
                if self.grid_layout.indexOf(old_widget) != -1:
                    self.grid_layout.removeWidget(old_widget)
                    old_widget.deleteLater()
            except (RuntimeError, AttributeError):
                # Widget has already been deleted
                continue
        
        old_widgets.clear()
        self.transitioning = False
        self.row_changed.emit(row)
        
        if hasattr(self.parent(), 'row_transition_timer'):
            self.parent().row_transition_timer.start()

    def on_animation_finished(self, old_widgets, row):
        """Handle animation finished event"""
        # Make a copy of the list before passing it
        self.finish_transition(old_widgets.copy(), row)

    def finish_transition(self, old_widgets, row):
        """Actually perform the transition cleanup"""
        
        for old_widget in old_widgets:
            if old_widget is None or sip.isdeleted(old_widget):
                continue
            
            try:
                # Check if widget still exists in the layout
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
        """Start the row transition sequence"""
        if not self.transitioning:
            self.load_images_for_row(0)
    
    def next_row(self):
        """Transition to the next row"""
        if self.transitioning:
            return
        
        next_row = (self.current_row + 1) % ROWS
        self.load_images_for_row(next_row)

    def replace_widget(self, old_widget):
        """Replace a deleted widget with a new image"""
        # Find the position of the old widget
        for row in range(ROWS):
            for col in range(COLS):
                item = self.grid_layout.itemAtPosition(row, col)
                if item and item.widget() == old_widget:
                    # Get a new image
                    new_images = get_next_images(1)
                    if new_images:
                        new_path = new_images[0]
                        # Mark as seen
                        mark_as_seen(new_path)
                        # Create new widget - not fading since it's replacing immediately
                        new_widget = ImageDisplay(new_path, self, self.replace_widget, is_fading=False)
                        # Add it at the same position
                        self.grid_layout.replaceWidget(old_widget, new_widget)
                        # Remove old widget
                        old_widget.deleteLater()
                        return
                    else:
                        # No more images, show placeholder
                        placeholder = QLabel("No More Images")
                        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        placeholder.setStyleSheet("color: #666; background-color: #1a1a1a; border-radius: 8px;")
                        placeholder.setMinimumSize(500, 500)
                        placeholder.setMaximumSize(500, 600)
                        self.grid_layout.replaceWidget(old_widget, placeholder)
                        old_widget.deleteLater()
                        return

# --- Add the required helper classes from the sample ---
class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, keybinder):
        self.keybinder = keybinder
        super().__init__()

    def nativeEventFilter(self, eventType, message):
        ret = self.keybinder.handler(eventType, message)
        return ret, 0
    
class EventDispatcher:
    """Install a native event filter to receive events from the OS"""

    def __init__(self, keybinder) -> None:
        self.win_event_filter = WinEventFilter(keybinder)
        self.event_dispatcher = QAbstractEventDispatcher.instance()
        self.event_dispatcher.installNativeEventFilter(self.win_event_filter)

class QtKeyBinder:
    def __init__(self, win_id: int | None) -> None:
        keybinder.init()
        self.win_id = win_id

        self.event_dispatcher = EventDispatcher(keybinder=keybinder)

    def register_hotkey(self, hotkey: str, callback) -> None:
        keybinder.register_hotkey(self.win_id, hotkey, callback)

    def unregister_hotkey(self, hotkey: str) -> None:
        keybinder.unregister_hotkey(self.win_id, hotkey)

class PhotoViewer(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Viewer - Crossfade Mode")
        self.setMinimumSize(5, 5)
        self.is_shrunk = False

        self.key_binder = QtKeyBinder(win_id=None)
        
        # Register the hotkey. The callback must be a regular callable,
        # but we can use a lambda that calls our slot.
        self.key_binder.register_hotkey('Alt+Z', self.toggle_window_size)
        
        # Transition settings
        self.transition_duration = 3000  # 3 seconds default
        self.row_transition_duration = 30000  # 30 seconds default between rows
        self.initial_delay = 30000
        
        # Initialize database
        init_db()
        refresh_list()
        
        # Setup UI
        self.setup_ui()

        # Start the slideshow after a short delay
        QTimer.singleShot(self.initial_delay, self.start_slideshow)

    @pyqtSlot()
    def toggle_window_size(self):
        """Toggle between normal and shrunk window size"""
        print("Shrink hotkey pressed")
        if not self.is_shrunk:
            self.showMinimized()
            self.is_shrunk = True
            self.enable_pause()
        else:
            self.showMaximized()
            self.is_shrunk = False
            self.disable_pause()
    
    def closeEvent(self, event):
        """Handle window close event - Clean up the key binder"""
        # Unregister the hotkey to be clean
        if hasattr(self, 'key_binder'):
            self.key_binder.unregister_hotkey('Alt+Z')
        if hasattr(self, 'row_transition_timer'):
            self.row_transition_timer.stop()
        event.accept()

    def changeEvent(self, event):
        """Handle window state changes to keep is_shrunk in sync"""
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                self.is_shrunk = True
                self.enable_pause()
            elif self.isMaximized() or self.isFullScreen():
                self.is_shrunk = False
                self.disable_pause()
        super().changeEvent(event)

    def setup_ui(self):
        """Setup the user interface"""
        # Central widget with main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top controls
        control_bar = QWidget()
        control_bar.setFixedHeight(80)  # Increased height to accommodate two sliders
        control_bar.setStyleSheet("""
            QWidget {
                background-color: #263238;
                border-bottom: 1px solid #333;
            }
        """)
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(20, 0, 20, 0)
        control_layout.setSpacing(15)
        
        # Status label
        self.status_label = QLabel("🔄 Crossfading - Row 1/3")
        self.status_label.setStyleSheet("color: #ccc; font-size: 14px; font-family: Arial, sans-serif;")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        
        # Create a container for the sliders with vertical layout
        sliders_container = QWidget()
        sliders_layout = QVBoxLayout(sliders_container)
        sliders_layout.setContentsMargins(0, 0, 0, 0)
        sliders_layout.setSpacing(5)
        
        # Row 1: Fade duration control
        fade_container = QWidget()
        fade_layout = QHBoxLayout(fade_container)
        fade_layout.setContentsMargins(0, 0, 0, 0)
        fade_layout.setSpacing(10)
        
        fade_label = QLabel("Fade Duration:")
        fade_label.setStyleSheet("color: #ccc; font-size: 13px;")
        fade_layout.addWidget(fade_label)
        
        self.fade_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_slider.setMinimum(1)   # 1 second
        self.fade_slider.setMaximum(10)  # 10 seconds
        self.fade_slider.setValue(3)     # Default to 3 seconds
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
        
        # Row 2: Row interval control
        interval_container = QWidget()
        interval_layout = QHBoxLayout(interval_container)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(10)
        
        interval_label = QLabel("Row Interval:")
        interval_label.setStyleSheet("color: #ccc; font-size: 13px;")
        interval_layout.addWidget(interval_label)
        
        self.interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.interval_slider.setMinimum(5)   # 5 seconds
        self.interval_slider.setMaximum(120)  # 120 seconds
        self.interval_slider.setValue(30)    # Default to 30 seconds
        self.interval_slider.setFixedWidth(150)
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
        
        self.interval_value_label = QLabel("30s")
        self.interval_value_label.setStyleSheet("color: #ccc; font-size: 13px; min-width: 30px;")
        interval_layout.addWidget(self.interval_value_label)
        
        sliders_layout.addWidget(interval_container)
        
        control_layout.addWidget(sliders_container)
        
        # Pause/Resume button
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
        
        # Timer for row transitions
        self.row_transition_timer = QTimer()
        self.row_transition_timer.setSingleShot(True)
        self.row_transition_timer.timeout.connect(self.image_grid.next_row)
        
        self.is_paused = False
        
    def start_slideshow(self):
        """Start the slideshow"""
        self.image_grid.start_row_sequence()
        
    def update_fade_duration(self, value):
        """Update the fade duration"""
        self.transition_duration = value * 1000  # Convert to milliseconds
        self.fade_value_label.setText(f"{value}s")
        
        # Update the grid's transition duration
        self.image_grid.set_transition_duration(self.transition_duration)
        
        # Note: Don't restart timer here, it will use the new duration on next transition
        
    def update_row_interval(self, value):
        """Update the row interval duration"""
        self.row_transition_duration = value * 1000  # Convert to milliseconds
        self.interval_value_label.setText(f"{value}s")
        
        # If timer is active, restart it with new duration
        if self.row_transition_timer.isActive() and not self.is_paused:
            # Calculate remaining time based on how much has elapsed
            # For simplicity, just restart the timer with new duration
            remaining = self.row_transition_timer.remainingTime()
            if remaining > 0:
                # Adjust based on proportion of old duration to new duration
                # Actually, let's just restart with new duration
                self.row_transition_timer.stop()
                self.row_transition_timer.start(self.row_transition_duration)
    
    def on_row_changed(self, row):
        """Called when a row transition completes"""
        self.status_label.setText(f"🔄 Crossfading - Row {row + 1}/{ROWS}")
        # Start timer for next row transition
        if not self.is_paused:
            self.row_transition_timer.start(self.row_transition_duration)
    
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
        self.row_transition_timer.stop()
        self.status_label.setText("⏸ Paused")

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
        # Resume the sequence only if not currently transitioning
        if not self.image_grid.transitioning:
            self.row_transition_timer.start(self.row_transition_duration)
        else:
            # If transitioning, the timer will start when transition completes
            self.status_label.setText("▶ Resumed - waiting for current transition...")

    def toggle_pause(self):
        """Toggle pause/resume"""
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
            self.row_transition_timer.stop()
            self.status_label.setText("⏸ Paused")
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
            # Resume the sequence only if not currently transitioning
            if not self.image_grid.transitioning:
                self.row_transition_timer.start(self.row_transition_duration)
            else:
                # If transitioning, the timer will start when transition completes
                self.status_label.setText("▶ Resumed - waiting for current transition...")
        
    def skip_row(self):
        """Skip to the next row immediately"""
        if not self.is_paused:
            self.row_transition_timer.stop()
            if not self.image_grid.transitioning:
                self.image_grid.next_row()
        
    def closeEvent(self, event):
        """Handle window close event"""
        self.row_transition_timer.stop()
        # Clean up keybind manager
        if hasattr(self, 'keybind_manager'):
            self.keybind_manager.deactivate()
        event.accept()

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = PhotoViewer()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()