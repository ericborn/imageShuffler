"""
Widget for displaying a single image with review overlay
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, 
    QGraphicsOpacityEffect, QSizePolicy, QWidget, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from image_utils import delete_image, load_image_pixmap
from fullscreen_viewer import FullscreenViewer
import os

class ImageDisplay(QFrame):
    """Widget for displaying a single image with review overlay"""
    
    def __init__(self, image_path, parent=None, delete_callback=None, is_fading=False):
        super().__init__(parent)
        self.image_path = image_path
        self.delete_callback = delete_callback
        self.is_fading = is_fading
        self.review_data = {
            'verdict': None,
            'fix_category': None,
            'fix_reason': ''
        }
        self.setup_ui()
        self.image_label.mousePressEvent = self.on_image_click
        
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
        overlay_layout.setContentsMargins(10, 10, 10, 10)
        overlay_layout.setSpacing(5)
        overlay_layout.addStretch()
        
        bottom_container = QVBoxLayout()
        bottom_container.setContentsMargins(0, 0, 0, 0)
        bottom_container.setSpacing(5)
        
        # Verdict buttons row
        verdict_container = QHBoxLayout()
        verdict_container.setSpacing(5)
        
        # Keeper button (Green)
        self.keeper_btn = QPushButton("✅ Keeper")
        self.keeper_btn.setFixedHeight(30)
        self.keeper_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(46, 204, 113, 0.8);
                color: white;
                border: 2px solid rgba(46, 204, 113, 0.8);
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: rgba(46, 204, 113, 1);
            }
            QPushButton[selected="true"] {
                background-color: rgba(46, 204, 113, 1);
                border: 2px solid white;
            }
        """)
        self.keeper_btn.clicked.connect(lambda: self.set_verdict('Keeper'))
        verdict_container.addWidget(self.keeper_btn)
        
        # Fixer button (Yellow)
        self.fixer_btn = QPushButton("🟡 Fixer")
        self.fixer_btn.setFixedHeight(30)
        self.fixer_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(241, 196, 15, 0.8);
                color: #333;
                border: 2px solid rgba(241, 196, 15, 0.8);
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: rgba(241, 196, 15, 1);
            }
            QPushButton[selected="true"] {
                background-color: rgba(241, 196, 15, 1);
                border: 2px solid white;
            }
        """)
        self.fixer_btn.clicked.connect(lambda: self.set_verdict('Fixer'))
        verdict_container.addWidget(self.fixer_btn)
        
        # Dud button (Red)
        self.dud_btn = QPushButton("🔴 Dud")
        self.dud_btn.setFixedHeight(30)
        self.dud_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(231, 76, 60, 0.8);
                color: white;
                border: 2px solid rgba(231, 76, 60, 0.8);
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: rgba(231, 76, 60, 1);
            }
            QPushButton[selected="true"] {
                background-color: rgba(231, 76, 60, 1);
                border: 2px solid white;
            }
        """)
        self.dud_btn.clicked.connect(lambda: self.set_verdict('Dud'))
        verdict_container.addWidget(self.dud_btn)
        
        bottom_container.addLayout(verdict_container)
        
        # Fix category dropdown (only visible for Fixer)
        self.fix_category_container = QHBoxLayout()
        self.fix_category_container.setSpacing(5)
        #self.fix_category_container.setVisible(False)
        
        fix_label = QLabel("Fix Category:")
        fix_label.setStyleSheet("color: white; font-size: 11px; background-color: rgba(0,0,0,0.5); padding: 2px 5px; border-radius: 3px;")
        self.fix_category_container.addWidget(fix_label)
        
        self.fix_category_combo = QComboBox()
        self.fix_category_combo.addItems(['', 'Anatomy', 'Background', 'Clothing', 'Lighting', 'Composition', 'Other'])
        self.fix_category_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 11px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: white;
                selection-background-color: #444;
            }
        """)
        self.fix_category_combo.currentTextChanged.connect(self.update_fix_category)
        self.fix_category_container.addWidget(self.fix_category_combo)
        
        bottom_container.addLayout(self.fix_category_container)
        
        # Fix reason text input (only visible for Fixer)
        self.fix_reason_container = QHBoxLayout()
        self.fix_reason_container.setSpacing(5)
        #self.fix_reason_container.setVisible(False)
        
        reason_label = QLabel("Reason:")
        reason_label.setStyleSheet("color: white; font-size: 11px; background-color: rgba(0,0,0,0.5); padding: 2px 5px; border-radius: 3px;")
        self.fix_reason_container.addWidget(reason_label)
        
        self.fix_reason_edit = QLineEdit()
        self.fix_reason_edit.setPlaceholderText("e.g., 'Mangled hands' or 'Poor composition'")
        self.fix_reason_edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 11px;
            }
        """)
        self.fix_reason_edit.textChanged.connect(self.update_fix_reason)
        self.fix_reason_container.addWidget(self.fix_reason_edit)
        
        bottom_container.addLayout(self.fix_reason_container)
        
        # Bottom row with stats and trash
        actions_container = QHBoxLayout()
        actions_container.setSpacing(5)
        
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
        actions_container.addWidget(self.stats_label)
        
        actions_container.addStretch()
        
        # Trash button
        self.trash_btn = QPushButton("🗑️")
        self.trash_btn.setFixedSize(30, 30)
        self.trash_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.8);
                border: none;
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 1);
            }
        """)
        self.trash_btn.clicked.connect(self.delete_image)
        actions_container.addWidget(self.trash_btn)
        
        bottom_container.addLayout(actions_container)
        
        # click event also added to overlay to prevent it from blocking the image click
        self.overlay.mousePressEvent = self.on_image_click
        
        overlay_layout.addLayout(bottom_container)
    
    def load_image(self):
        pixmap = load_image_pixmap(self.image_path)
        if pixmap:
            self.insert_into_db()
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
    
    def set_verdict(self, verdict):
        """Set the verdict and update button states"""
        self.review_data['verdict'] = verdict
        
        # Update button styles
        self.keeper_btn.setProperty("selected", verdict == 'Keeper')
        self.fixer_btn.setProperty("selected", verdict == 'Fixer')
        self.dud_btn.setProperty("selected", verdict == 'Dud')
        
        for btn in [self.keeper_btn, self.fixer_btn, self.dud_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        # Show/hide fix details based on verdict
        is_fixer = verdict == 'Fixer'
        # self.fix_category_container.setVisible(is_fixer)
        # self.fix_reason_container.setVisible(is_fixer)
        
        # Save review to database if image is in database
        self.save_review_to_db()
    
    def update_fix_category(self, category):
        self.review_data['fix_category'] = category if category else None
        self.save_review_to_db()
    
    def update_fix_reason(self, reason):
        self.review_data['fix_reason'] = reason
        self.save_review_to_db()

    def insert_into_db(self):
        import image_database as idb
        from image_utils import get_images_path
        
        # Get image ID from file path
        abs_path = os.path.join(get_images_path(), self.image_path)

        # Find the image in the database
        result = idb.find_image(abs_path)

        if not result:
            # Image not in database yet - import it
            from sd_parsers import ParserManager
            parser_manager = ParserManager()
            metadata = idb.extract_metadata_from_image(abs_path, parser_manager)
            image_id = idb.insert_image(metadata)
            
            # Parse and insert layers
            if metadata['positive_prompt'] and metadata['positive_prompt'] not in ['NO_METADATA', 'ERROR']:
                layers = idb.parse_prompt_layers(metadata['positive_prompt'])
                for layer in layers:
                    layer['image_id'] = image_id
                    idb.insert_layer_evaluation(layer)

    def save_review_to_db(self):
        """Save the review data to the database"""
        try:
            from image_database import update_image_review, find_image
            from image_utils import get_images_path
            
            # Get image ID from file path
            abs_path = os.path.join(get_images_path(), self.image_path)
            
            # Find the image in the database
            result = find_image(abs_path)
            
            if result:
                image_id = result[0]
                if self.review_data['verdict']:
                    update_image_review(image_id, self.review_data)
            else:
                self.insert_into_db()
                if self.review_data['verdict']:
                    update_image_review(image_id, self.review_data)
            
        except Exception as e:
            print(f"Error saving review to database: {e}")
    
    def delete_image(self):
        reply = QMessageBox.question(
            self, 'Delete Image',
            'Are you sure you want to delete this image?\n\n'
            'Note: Review data will be preserved for analysis.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if delete_image(self.image_path):
                if self.delete_callback:
                    self.delete_callback(self)
                self.deleteLater()
    
    def update_stats_label(self):
        """Update the stats label with times displayed count"""
        try:
            from image_utils import get_images_path
            import sqlite3
            
            abs_path = os.path.join(get_images_path(), self.image_path)
            db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'image_evaluations.db')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT times_displayed FROM image_details WHERE file_path = ?", (abs_path,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                self.stats_label.setText(f"👁 {result[0]}")
            else:
                self.stats_label.setText("👁 0")
        except:
            self.stats_label.setText("👁 ?")
    
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

    def on_image_click(self, event):
        """Handle clicking on the image to open fullscreen viewer"""
        # Pause the slideshow in the parent
        if self.parent():
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'pause_slideshow'):
                main_window.pause_slideshow()
        
        # Open fullscreen viewer
        fullscreen = FullscreenViewer(
            self.image_path, 
            parent=self, 
            on_close_callback=self.on_fullscreen_close
        )
        fullscreen.show()

    def on_fullscreen_close(self):
        """Called when fullscreen viewer closes"""
        if self.parent():
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'resume_after_fullscreen'):
                main_window.resume_after_fullscreen()
                
    def get_main_window(self):
        """Find the main window in the widget hierarchy"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'image_grid') and hasattr(parent, 'row_transition_timer'):
                return parent
            parent = parent.parent()
        return None