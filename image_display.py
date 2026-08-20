"""
Widget for displaying a single image with overlay buttons
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, 
    QGraphicsOpacityEffect, QSizePolicy, QWidget
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from database import toggle_favorite, is_favorited, toggle_like, is_liked, get_image_stats
from image_utils import delete_image, load_image_pixmap
import os

class ImageDisplay(QFrame):
    """Widget for displaying a single image with overlay buttons"""
    
    def __init__(self, image_path, parent=None, delete_callback=None, is_fading=False):
        super().__init__(parent)
        self.image_path = image_path
        self.is_favorited = is_favorited(image_path)
        self.is_liked = is_liked(image_path)
        self.delete_callback = delete_callback
        self.is_fading = is_fading
        self.stats = get_image_stats(image_path)
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
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent; border: none;")
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed
        )
        
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(1.0)
        self.image_label.setGraphicsEffect(self.opacity_effect)
        
        layout.addWidget(self.image_label)
        
        # Overlay
        self.setup_overlay()
        self.load_image()
        
        # Hover timer
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.show_overlay)
        
    def setup_overlay(self):
        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0); border-radius: 8px;")
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setVisible(False)
        
        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(15, 10, 15, 15)
        overlay_layout.setSpacing(5)
        overlay_layout.addStretch()
        
        bottom_container = QHBoxLayout()
        bottom_container.setContentsMargins(0, 0, 0, 0)
        bottom_container.setSpacing(5)
        
        # Heart button
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
        
        # Stats label
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            color: white;
            background-color: rgba(0, 0, 0, 0.6);
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
        """)
        self.update_stats_label()
        bottom_container.addWidget(self.stats_label)
        
        # Like button
        self.like_btn = QPushButton()
        self.like_btn.setFixedSize(35, 35)
        self.update_like_button()
        self.like_btn.clicked.connect(self.toggle_like)
        bottom_container.addWidget(self.like_btn)
        
        bottom_container.addStretch()
        
        # Trash button
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
    
    def load_image(self):
        pixmap = load_image_pixmap(self.image_path)
        if pixmap:
            aspect_ratio = pixmap.height() / pixmap.width()
            if aspect_ratio >= 1.2:
                self.setMaximumSize(500, 600)
                self.setMinimumSize(500, 600)
            else:
                self.setMaximumSize(500, 500)
                self.setMinimumSize(500, 500)
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setText("📷\nNo Image")
            self.image_label.setStyleSheet("color: #666; font-size: 20px;")
    
    def toggle_favorite(self):
        self.is_favorited = toggle_favorite(self.image_path)
        self.heart_btn.setProperty("favorited", self.is_favorited)
        self.heart_btn.style().unpolish(self.heart_btn)
        self.heart_btn.style().polish(self.heart_btn)

    def toggle_like(self):
        self.is_liked = toggle_like(self.image_path)
        self.update_like_button()

    def delete_image(self):
        reply = QMessageBox.question(
            self, 'Delete Image',
            'Are you sure you want to delete this image?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if delete_image(self.image_path):
                if self.delete_callback:
                    self.delete_callback(self)
                self.deleteLater()

    def update_like_button(self):
        like_icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', 'like.png')
        if os.path.exists(like_icon_path):
            icon = QIcon(like_icon_path)
            self.like_btn.setIcon(icon)
            self.like_btn.setIconSize(QSize(20, 20))
        else:
            self.like_btn.setText("👍" if self.is_liked else "🤍")
        
        if self.is_liked:
            self.like_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(52, 152, 219, 0.9);
                    border: none;
                    border-radius: 17px;
                }
                QPushButton:hover {
                    background-color: rgba(52, 152, 219, 1);
                }
            """)
        else:
            self.like_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.8);
                    border: none;
                    border-radius: 17px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 1);
                }
            """)
        self.stats = get_image_stats(self.image_path)
        self.update_stats_label()
    
    def update_stats_label(self):
        self.stats = get_image_stats(self.image_path)
        self.stats_label.setText(f"👁 {self.stats['times_displayed']}  ❤ {self.stats['liked']}")
    
    def get_opacity_effect(self):
        return self.opacity_effect
    
    def set_fading(self, fading):
        self.is_fading = fading
        if fading:
            self.overlay.setVisible(False)
            self.hover_timer.stop()
    
    def enterEvent(self, event):
        if not self.is_fading:
            self.hover_timer.start(200)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.hover_timer.stop()
        self.overlay.setVisible(False)
        super().leaveEvent(event)
        
    def show_overlay(self):
        self.overlay.setVisible(True)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(0, 0, self.width(), self.height())