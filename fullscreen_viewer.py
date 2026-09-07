"""
Fullscreen single image viewer with review interface
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QSizePolicy, QGridLayout, QLayout,
    QComboBox, QLineEdit, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from image_utils import load_image_pixmap, get_images_path
import os
import sqlite3

class FullscreenViewer(QWidget):
    """Fullscreen popup for viewing a single image with review interface"""
    
    def __init__(self, image_path, parent=None, on_close_callback=None):
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.image_path = image_path
        self.parent_widget = parent
        self.on_close_callback = on_close_callback
        self.review_data = {
            'verdict': None,
            'fix_category': None,
            'fix_reason': ''
        }
        self.setup_ui()
        self.load_review_data()
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
        top_bar.setStyleSheet("background-color: rgba(0, 0, 0, 0.8);")
        top_bar.setFixedHeight(50)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        
        # Title
        title_label = QLabel("📋 Image Review")
        title_label.setStyleSheet("color: #FFB74D; font-size: 18px; font-weight: bold;")
        top_layout.addWidget(title_label)
        
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
        
        # Main content area (image + review panel)
        content_container = QWidget()
        content_container.setStyleSheet("background-color: #0a0a0a;")
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)
        
        # Image display (left side)
        image_container = QWidget()
        image_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.load_image()
        image_layout.addWidget(self.image_label)
        
        content_layout.addWidget(image_container, 3)  # 3 parts of the space
        
        # Review panel (right side)
        review_panel = QWidget()
        review_panel.setMaximumWidth(500)
        review_panel.setMinimumWidth(350)
        review_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 30, 0.95);
                border-radius: 8px;
            }
        """)
        review_layout = QVBoxLayout(review_panel)
        review_layout.setContentsMargins(20, 20, 20, 20)
        review_layout.setSpacing(15)
        
        # Prompt display section
        prompt_label = QLabel("📝 Prompt")
        prompt_label.setStyleSheet("color: #FFB74D; font-size: 16px; font-weight: bold;")
        review_layout.addWidget(prompt_label)
        
        # Prompt text area
        self.prompt_display = QTextEdit()
        self.prompt_display.setReadOnly(True)
        self.prompt_display.setMaximumHeight(120)
        self.prompt_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.5);
                color: #ccc;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        self.load_prompt()
        review_layout.addWidget(self.prompt_display)
        
        # Layer breakdown
        layer_label = QLabel("📊 Layer Breakdown")
        layer_label.setStyleSheet("color: #FFB74D; font-size: 16px; font-weight: bold;")
        review_layout.addWidget(layer_label)
        
        # Layer scroll area
        layer_scroll = QScrollArea()
        layer_scroll.setStyleSheet("""
            QScrollArea {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        layer_scroll.setMaximumHeight(150)
        layer_scroll.setWidgetResizable(True)
        
        layer_container = QWidget()
        layer_layout = QVBoxLayout(layer_container)
        layer_layout.setSpacing(3)
        layer_layout.setContentsMargins(5, 5, 5, 5)
        
        self.layer_widgets = []
        self.load_layers(layer_layout)
        
        layer_scroll.setWidget(layer_container)
        review_layout.addWidget(layer_scroll)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #333;")
        review_layout.addWidget(separator)
        
        # Review verdict section
        verdict_label = QLabel("⭐ Your Review")
        verdict_label.setStyleSheet("color: #FFB74D; font-size: 16px; font-weight: bold;")
        review_layout.addWidget(verdict_label)
        
        # Verdict buttons
        verdict_container = QHBoxLayout()
        verdict_container.setSpacing(8)
        
        self.keeper_btn = QPushButton("✅ Keeper")
        self.keeper_btn.setFixedHeight(35)
        self.keeper_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(46, 204, 113, 0.6);
                color: white;
                border: 2px solid rgba(46, 204, 113, 0.6);
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(46, 204, 113, 0.9);
            }
            QPushButton[selected="true"] {
                background-color: rgba(46, 204, 113, 1);
                border: 2px solid white;
            }
        """)
        self.keeper_btn.clicked.connect(lambda: self.set_verdict('Keeper'))
        verdict_container.addWidget(self.keeper_btn)
        
        self.fixer_btn = QPushButton("🟡 Fixer")
        self.fixer_btn.setFixedHeight(35)
        self.fixer_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(241, 196, 15, 0.6);
                color: #333;
                border: 2px solid rgba(241, 196, 15, 0.6);
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(241, 196, 15, 0.9);
            }
            QPushButton[selected="true"] {
                background-color: rgba(241, 196, 15, 1);
                border: 2px solid white;
            }
        """)
        self.fixer_btn.clicked.connect(lambda: self.set_verdict('Fixer'))
        verdict_container.addWidget(self.fixer_btn)
        
        self.dud_btn = QPushButton("🔴 Dud")
        self.dud_btn.setFixedHeight(35)
        self.dud_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(231, 76, 60, 0.6);
                color: white;
                border: 2px solid rgba(231, 76, 60, 0.6);
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(231, 76, 60, 0.9);
            }
            QPushButton[selected="true"] {
                background-color: rgba(231, 76, 60, 1);
                border: 2px solid white;
            }
        """)
        self.dud_btn.clicked.connect(lambda: self.set_verdict('Dud'))
        verdict_container.addWidget(self.dud_btn)
        
        review_layout.addLayout(verdict_container)
        
        # Fix category dropdown (only visible for Fixer)
        self.fix_category_widget = QWidget()
        self.fix_category_container = QHBoxLayout(self.fix_category_widget)
        self.fix_category_container.setSpacing(8)
        self.fix_category_widget.setVisible(False)
        
        fix_label = QLabel("Fix Category:")
        fix_label.setStyleSheet("color: #ccc; font-size: 13px;")
        self.fix_category_container.addWidget(fix_label)
        
        self.fix_category_combo = QComboBox()
        self.fix_category_combo.addItems(['', 'Anatomy', 'Background', 'Clothing', 'Lighting', 'Composition', 'Other'])
        self.fix_category_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
                font-size: 12px;
                min-width: 120px;
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
        self.fix_category_container.addStretch()
        
        review_layout.addLayout(self.fix_category_container)
        
        # Fix reason text input (only visible for Fixer)
        self.fix_reason_widget = QWidget()
        self.fix_reason_container = QVBoxLayout(self.fix_reason_widget)
        self.fix_reason_container.setSpacing(5)
        self.fix_reason_widget.setVisible(False)
        
        reason_label = QLabel("Fix Reason:")
        reason_label.setStyleSheet("color: #ccc; font-size: 13px;")
        self.fix_reason_container.addWidget(reason_label)
        
        self.fix_reason_edit = QLineEdit()
        self.fix_reason_edit.setPlaceholderText("e.g., 'Mangled hands' or 'Poor composition'")
        self.fix_reason_edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        self.fix_reason_edit.textChanged.connect(self.update_fix_reason)
        self.fix_reason_container.addWidget(self.fix_reason_edit)
        
        review_layout.addLayout(self.fix_reason_container)
        
        review_layout.addStretch()
        
        # Metadata section
        metadata_label = QLabel("ℹ️ Metadata")
        metadata_label.setStyleSheet("color: #FFB74D; font-size: 14px; font-weight: bold;")
        review_layout.addWidget(metadata_label)
        
        self.metadata_display = QTextEdit()
        self.metadata_display.setReadOnly(True)
        self.metadata_display.setMaximumHeight(80)
        self.metadata_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.5);
                color: #888;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
            }
        """)
        self.load_metadata()
        review_layout.addWidget(self.metadata_display)
        
        content_layout.addWidget(review_panel, 1)  # 1 part of the space
        
        main_layout.addWidget(content_container)
    
    def load_image(self):
        """Load and display the image"""
        screen = self.screen()
        if screen:
            screen_geometry = screen.geometry()
            max_width = screen_geometry.width() - 420  # Account for review panel
            max_height = screen_geometry.height() - 160  # Account for top bar
        else:
            max_width = 1080
            max_height = 1920
        
        abs_path = os.path.join(get_images_path(), self.image_path)
        if os.path.exists(abs_path):
            pixmap = QPixmap(abs_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    max_width, max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                return
        
        self.image_label.setText("📷\nImage Not Found")
        self.image_label.setStyleSheet("color: #666; font-size: 24px; background-color: #0a0a0a;")
    
    def load_prompt(self):
        """Load prompt from database"""
        try:
            abs_path = os.path.join(get_images_path(), self.image_path)
            db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'image_evaluations.db')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT positive_prompt FROM image_details WHERE file_path = ?", (abs_path,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                self.prompt_display.setText(result[0])
            else:
                self.prompt_display.setText("No prompt data available")
        except Exception as e:
            self.prompt_display.setText(f"Error loading prompt: {e}")
    
    def load_layers(self, layout):
        """Load layer breakdown from database"""
        try:
            abs_path = os.path.join(get_images_path(), self.image_path)
            db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'image_evaluations.db')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT layer_number, layer_category, layer_text, execution_status, conflict_type, is_dominant
                FROM layer_evaluations le
                JOIN image_details id ON le.image_id = id.image_id
                WHERE id.file_path = ?
                ORDER BY layer_number
            """, (abs_path,))
            results = cursor.fetchall()
            conn.close()
            
            if results:
                for row in results:
                    layer_widget = QLabel(f"{row[1]}: {row[2][:50]}{'...' if len(row[2]) > 50 else ''}")
                    layer_widget.setStyleSheet("""
                        color: #aaa;
                        background-color: rgba(0, 0, 0, 0.3);
                        padding: 2px 8px;
                        border-radius: 3px;
                        font-size: 11px;
                    """)
                    layout.addWidget(layer_widget)
                    self.layer_widgets.append(layer_widget)
            else:
                no_layers = QLabel("No layer data available. Prompt may not be in colon-delimited format.")
                no_layers.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
                layout.addWidget(no_layers)
                self.layer_widgets.append(no_layers)
        except Exception as e:
            error_label = QLabel(f"Error loading layers: {e}")
            error_label.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
            layout.addWidget(error_label)
            self.layer_widgets.append(error_label)
    
    def load_metadata(self):
        """Load metadata from database"""
        try:
            abs_path = os.path.join(get_images_path(), self.image_path)
            db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'image_evaluations.db')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT model, steps, scheduler, cfg, seed, loras
                FROM image_details WHERE file_path = ?
            """, (abs_path,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                model, steps, scheduler, cfg, seed, loras = result
                metadata = f"Model: {model or 'N/A'}\n"
                metadata += f"Steps: {steps or 'N/A'} | Scheduler: {scheduler or 'N/A'}\n"
                metadata += f"CFG: {cfg or 'N/A'} | Seed: {seed or 'N/A'}"
                if loras:
                    metadata += f"\nLoRAs: {loras}"
                metadata += "\n" + abs_path
                self.metadata_display.setText(metadata)
            else:
                self.metadata_display.setText("No metadata available")
        except Exception as e:
            self.metadata_display.setText(f"Error loading metadata: {e}")
    
    def load_review_data(self):
        """Load existing review data from database"""
        try:
            abs_path = os.path.join(get_images_path(), self.image_path)
            db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'image_evaluations.db')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT verdict, fix_category, fix_reason
                FROM image_details WHERE file_path = ?
            """, (abs_path,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                verdict, fix_category, fix_reason = result
                self.review_data['verdict'] = verdict
                self.review_data['fix_category'] = fix_category
                self.review_data['fix_reason'] = fix_reason or ''
                
                # Update UI
                self.set_verdict(verdict, restore_data=True)
                if fix_category:
                    self.fix_category_combo.setCurrentText(fix_category)
                if fix_reason:
                    self.fix_reason_edit.setText(fix_reason)
        except Exception as e:
            print(f"Error loading review data: {e}")
    
    def set_verdict(self, verdict, restore_data=False):
        """Set the verdict and update button states"""
        if not restore_data:
            self.review_data['verdict'] = verdict
        
        self.keeper_btn.setProperty("selected", verdict == 'Keeper')
        self.fixer_btn.setProperty("selected", verdict == 'Fixer')
        self.dud_btn.setProperty("selected", verdict == 'Dud')
        
        for btn in [self.keeper_btn, self.fixer_btn, self.dud_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        is_fixer = verdict == 'Fixer'
        self.fix_category_widget.setVisible(is_fixer)
        self.fix_reason_widget.setVisible(is_fixer)
        
        if not restore_data:
            self.save_review_to_db()
    
    def update_fix_category(self, category):
        self.review_data['fix_category'] = category if category else None
        self.save_review_to_db()
    
    def update_fix_reason(self, reason):
        self.review_data['fix_reason'] = reason
        self.save_review_to_db()
    
    def save_review_to_db(self):
        """Save the review data to the database"""
        try:
            import image_database as idb
            from image_utils import get_images_path
            
            # Get image ID from file path
            abs_path = os.path.join(get_images_path(), self.image_path)
            
            # Find the image in the database
            result = idb.find_image(abs_path)
            
            if result:
                image_id = result[0]
                # Only save if we have a verdict
                if self.review_data['verdict']:
                    idb.update_image_review(image_id, self.review_data)
            else:
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
                
                # Now save the review
                if self.review_data['verdict']:
                    idb.update_image_review(image_id, self.review_data)
            
        except Exception as e:
            print(f"Error saving review to database: {e}")
    
    def close_viewer(self):
        """Close the fullscreen viewer and resume slideshow"""
        if self.parent_widget and hasattr(self.parent_widget, 'resume_after_fullscreen'):
            self.parent_widget.resume_after_fullscreen()
        
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
    
    def resizeEvent(self, event):
        """Handle resize to update image"""
        super().resizeEvent(event)
        self.load_image()