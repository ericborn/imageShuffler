"""
Database operations for the photo viewer
"""
import sqlite3
import os
from image_utils import normalize_path

DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'favorites.db')

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
            times_displayed INTEGER DEFAULT 0,
            liked INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def toggle_favorite(image_path):
    """Toggle favorite status for an image"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_id = os.path.basename(image_path)
    abs_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', image_path)
    
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

def toggle_like(image_path):
    """Toggle like status for an image"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_id = os.path.basename(image_path)
    abs_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', image_path)
    
    cursor.execute('SELECT liked FROM favorites WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    
    if result:
        new_status = 0 if result[0] == 1 else 1
        cursor.execute(
            'UPDATE favorites SET liked = ? WHERE image_id = ?',
            (new_status, image_id)
        )
    else:
        new_status = 1
        cursor.execute(
            'INSERT INTO favorites (image_id, filename, liked) VALUES (?, ?, ?)',
            (image_id, normalize_path(abs_path), new_status)
        )
    
    conn.commit()
    conn.close()
    return bool(new_status)

def is_liked(image_path):
    """Check if an image is liked"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = os.path.basename(image_path)
    
    cursor.execute('SELECT liked FROM favorites WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    conn.close()
    
    return bool(result[0]) if result else False

def get_image_stats(image_path):
    """Get image statistics from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = os.path.basename(image_path)
    
    cursor.execute('SELECT times_displayed, liked FROM favorites WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {'times_displayed': result[0], 'liked': result[1] if result[1] is not None else 0}
    return {'times_displayed': 0, 'liked': 0}

def mark_as_seen(image_path):
    """Mark an image as seen in the database by incrementing times_displayed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_id = os.path.basename(image_path)
    abs_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', image_path)
    
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

def delete_from_db(image_path):
    """Remove image from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = os.path.basename(image_path)
    cursor.execute('DELETE FROM favorites WHERE image_id = ?', (image_id,))
    conn.commit()
    conn.close()