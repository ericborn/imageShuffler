"""
Image loading and management utilities
"""
import os
import glob
import random
import re
from send2trash import send2trash
from sd_parsers import ParserManager

# Global state
all_images = []
current_index = 0
BATCH_SIZE = 30
ROWS = 3
COLS = 2
IMAGES_PER_VIEW = ROWS * COLS

def extract_prompt_info(image_path):
    # Initialize the parser manager
    parser_manager = ParserManager()

    # Initialize empty list to store parsed data
    parsed_data = []

    prompt_info = parser_manager.parse(image_path)
    prompt_string = prompt_info.full_prompt if hasattr(prompt_info, 'full_prompt') else ''

    # return early if string empty
    if prompt_string == '':
        return prompt_string

    # remove trailing whitespace
    prompt_string = prompt_string.strip()

    # remove consecutive commas with no text
    while True:
        collapsed = re.sub(r',\s*,', ',', prompt_string)
        if collapsed == prompt_string:
            break
        prompt_string = collapsed

    # remove trailing commas and add space between comma separated values
    prompt_string = re.sub(r',+$', '', prompt_string)
    prompt_string = re.sub(r',\s*(?!$)', ', ', prompt_string)

    return prompt_string

def normalize_path(file_path):
    """Convert any path to use forward slashes"""
    return file_path.replace('\\', '/')

def get_images_path():
    """Get the path to the images directory"""
    path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(path, 'static')

def refresh_list():
    """Refresh the master list of all images"""
    global all_images, current_index
    
    images_path = get_images_path()
    image_files = []
    
    if os.path.exists(images_path):
        for root, dirs, files in os.walk(images_path):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                    # Skip UI icons
                    if file in ['heart.png', 'trash.png', 'like.png']:
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, images_path)
                    image_files.append(normalize_path(rel_path))
    
    if not image_files:
        return []
    
    # Separate images into never seen and seen
    from image_database import get_image_stats
    never_seen = []
    seen = []
    
    # Also check the new database for times_displayed
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'image_evaluations.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for img_path in image_files:
            abs_path = os.path.join(images_path, img_path)
            cursor.execute("SELECT times_displayed FROM image_details WHERE file_path = ?", (abs_path,))
            result = cursor.fetchone()
            
            if result and result[0] > 0:
                seen.append(img_path)
            else:
                # Check old database as fallback
                stats = get_image_stats(img_path)
                if stats['times_displayed'] == 0:
                    never_seen.append(img_path)
                else:
                    seen.append(img_path)
        
        conn.close()
    except Exception as e:
        print(f"Error checking times_displayed: {e}")
        # Fallback to old behavior
        for img_path in image_files:
            stats = get_image_stats(img_path)
            if stats['times_displayed'] == 0:
                never_seen.append(img_path)
            else:
                seen.append(img_path)
    
    random.shuffle(never_seen)
    random.shuffle(seen)
    
    all_images = never_seen + seen
    current_index = 0
    
    return all_images

def get_next_images(count=None):
    """Get next batch of images for display"""
    from image_database import mark_as_seen
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
    
    if len(selected) < count and len(all_images) > 0:
        remaining = count - len(selected)
        end_index = min(remaining, len(all_images))
        selected.extend(all_images[0:end_index])
        current_index = end_index
    
    # Mark as seen
    for img in selected:
        mark_as_seen(img)
    
    return selected

def delete_image(image_path):
    """Delete an image from disk but preserve database records for analysis"""
    from image_database import mark_deleted  # Keep the old function but we'll modify it
    
    abs_path = os.path.join(get_images_path(), image_path)
    abs_path = os.path.normpath(abs_path)
    
    if os.path.exists(abs_path):
        send2trash(abs_path)
    
    # Mark the image as deleted in the new database, but don't delete the record
    mark_deleted(image_path)
    return True

def load_image_pixmap(image_path, target_width=500, target_height=500):
    """Load and scale an image for display"""
    from PyQt6.QtGui import QPixmap, QPainter
    from PyQt6.QtCore import Qt
    
    abs_path = os.path.join(get_images_path(), image_path)
    if os.path.exists(abs_path):
        pixmap = QPixmap(abs_path)
        if not pixmap.isNull():
            img_width = pixmap.width()
            img_height = pixmap.height()
            aspect_ratio = img_height / img_width
            
            if aspect_ratio >= 1.2:
                target_height = 600
            
            scaled_pixmap = pixmap.scaled(
                target_width, target_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            final_pixmap = QPixmap(target_width, target_height)
            final_pixmap.fill(Qt.GlobalColor.transparent)
            
            x = (target_width - scaled_pixmap.width()) // 2
            y = (target_height - scaled_pixmap.height()) // 2
            
            painter = QPainter(final_pixmap)
            painter.drawPixmap(x, y, scaled_pixmap)
            painter.end()
            
            return final_pixmap
    return None