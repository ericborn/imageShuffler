"""
Image loading and management utilities
"""
import os
import glob
import random
from send2trash import send2trash
from sd_parsers import ParserManager

# Global state
all_images = []
current_index = 0
BATCH_SIZE = 30
ROWS = 3
COLS = 2
IMAGES_PER_VIEW = ROWS * COLS

def extract_prompt_info(file_path):
    # Initialize the parser manager
    parser_manager = ParserManager()

    # Initialize empty list to store parsed data
    parsed_data = []

    prompt_info = parser_manager.parse(file_path)

    # to string
    prompt_string = prompt_info.full_prompt if hasattr(prompt_info, 'full_prompt') else ''

    # convert to list, separate by comma
    prompt_list = [item.strip() for item in prompt_string.split(',')]

    # remove empty rows
    prompt_list = [item for item in prompt_list if item]
    return prompt_list

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
                    if file == 'heart.png' or file == 'trash.png' or file == 'like.png':
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, images_path)
                    image_files.append(normalize_path(rel_path))
    
    if not image_files:
        return []
    
    # Separate images into never seen and seen
    from database import get_image_stats
    never_seen = []
    seen = []

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
    from database import mark_as_seen
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
    """Delete an image from disk and remove from favorites"""
    from database import delete_from_db
    abs_path = os.path.join(get_images_path(), image_path)
    abs_path = os.path.normpath(abs_path)
    
    if os.path.exists(abs_path):
        send2trash(abs_path)
    
    delete_from_db(image_path)
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