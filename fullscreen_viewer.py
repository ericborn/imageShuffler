# fullscreen_viewer.py
"""
Fullscreen single image viewer with prompt word toggles
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from database import get_image_prompt, get_selected_prompt_words, toggle_prompt_word
from image_utils import load_image_pixmap, get_images_path
import os

class PromptWordButton(QPushButton):
    """Toggle button for prompt words"""
    
    def __init__(self, word, image_path, parent=None):
        super().__init__(word, parent)
        self.word = word
        self.image_path = image_path
        self.is_selected = word in get_selected_prompt_words(image_path)
        self.setCheckable(True)
        self.setChecked(self.is_selected)
        self.update_style()
        self.clicked.connect(self.toggle_selection)
        
    def update_style(self):
        if self.is_selected:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 2px solid #4CAF50;
                    border-radius: 15px;
                    padding: 8px 16px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #333;
                    color: #ccc;
                    border: 2px solid #555;
                    border-radius: 15px;
                    padding: 8px 16px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #444;
                    border-color: #666;
                }
            """)
    
    def toggle_selection(self):
        self.is_selected = toggle_prompt_word(self.image_path, self.word)
        self.setChecked(self.is_selected)
        self.update_style()

class FullscreenViewer(QWidget):
    """Fullscreen popup for viewing a single image with prompt words"""
    
    def __init__(self, image_path, parent=None, on_close_callback=None):
        print("full screen viewer init called!")
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.image_path = image_path
        self.parent_widget = parent
        self.on_close_callback = on_close_callback
        self.setup_ui()
        self.showFullScreen()
        
    def setup_ui(self):
        """Setup the fullscreen UI"""
        self.setStyleSheet("background-color: #1a1a1a;")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top bar with close button
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
        top_bar.setFixedHeight(50)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        
        # Spacer to push close button to right
        top_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 20px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 50, 50, 0.3);
                border-color: rgba(255, 50, 50, 0.8);
            }
        """)
        close_btn.clicked.connect(self.close_viewer)
        top_layout.addWidget(close_btn)
        
        main_layout.addWidget(top_bar)
        
        # Image display area
        image_container = QWidget()
        image_container.setStyleSheet("background-color: #0a0a0a;")
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load and display image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.load_image()
        image_layout.addWidget(self.image_label)
        
        main_layout.addWidget(image_container, 1)  # Give it stretch factor
        
        # Bottom bar for prompt words
        bottom_bar = QWidget()
        bottom_bar.setStyleSheet("background-color: rgba(0, 0, 0, 0.85);")
        bottom_bar.setMinimumHeight(150)
        bottom_bar.setMaximumHeight(300)
        
        bottom_layout = QVBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(20, 15, 20, 15)
        bottom_layout.setSpacing(10)
        
        # Prompt label
        prompt_label = QLabel("📝 Prompt Words:")
        prompt_label.setStyleSheet("color: #FFB74D; font-size: 16px; font-weight: bold;")
        bottom_layout.addWidget(prompt_label)
        
        # Scroll area for word buttons
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                height: 10px;
                background: #2a2a2a;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #555;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #777;
            }
        """)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Widget to hold word buttons
        word_container = QWidget()
        word_container.setStyleSheet("background-color: transparent;")
        word_layout = QHBoxLayout(word_container)
        word_layout.setContentsMargins(5, 5, 5, 5)
        word_layout.setSpacing(10)
        word_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Get prompt words
        prompt_words = get_image_prompt(self.image_path)
        
        if prompt_words:
            for word in prompt_words:
                word_btn = PromptWordButton(word.strip(), self.image_path, self)
                word_layout.addWidget(word_btn)
        else:
            no_prompt_label = QLabel("No prompt words available for this image")
            no_prompt_label.setStyleSheet("color: #666; font-size: 14px;")
            word_layout.addWidget(no_prompt_label)
        
        # Add stretch to push words to left
        word_layout.addStretch()
        
        scroll_area.setWidget(word_container)
        bottom_layout.addWidget(scroll_area)
        
        main_layout.addWidget(bottom_bar)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
    
    def load_image(self):
        """Load and display the image fullscreen"""
        # Get screen size
        screen = self.screen()
        if screen:
            screen_geometry = screen.geometry()
            max_width = screen_geometry.width() - 40
            max_height = screen_geometry.height() - 220  # Account for top and bottom bars
        else:
            max_width = 1080
            max_height = 1920
        
        # Load image
        abs_path = os.path.join(get_images_path(), self.image_path)
        if os.path.exists(abs_path):
            pixmap = QPixmap(abs_path)
            if not pixmap.isNull():
                # Scale to fit screen while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    max_width, max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                return
        
        # Show placeholder if image can't be loaded
        self.image_label.setText("📷\nImage Not Found")
        self.image_label.setStyleSheet("color: #666; font-size: 24px; background-color: #0a0a0a;")
    
    def close_viewer(self):
        """Close the fullscreen viewer and resume slideshow"""
        # Resume slideshow in parent
        if self.parent_widget and hasattr(self.parent_widget, 'resume_after_fullscreen'):
            self.parent_widget.resume_after_fullscreen()
        
        # Call the close callback if provided
        if self.on_close_callback:
            self.on_close_callback()
        
        self.close()
    
    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key.Key_Escape:
            self.close_viewer()
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle close event"""
        self.close_viewer()
        super().closeEvent(event)