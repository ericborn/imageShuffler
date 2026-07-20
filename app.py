# -*- coding: utf-8 -*-
"""
Created on Thu Dec  7 14:53:54 2023
@author: eric
"""

import os
import glob
import random
import sqlite3
from send2trash import send2trash
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

path = os.path.dirname(os.path.realpath(__file__))

# Database setup
DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'favorites.db')

# Global variables
all_images = []
current_index = 0
BATCH_SIZE = 20  # Load more images at once for smooth scrolling

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
            times_displayed INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def toggle_favorite(image_path):
    """Toggle favorite status for an image"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    formatted_path = normalize_path(image_path)
    image_id = os.path.basename(image_path)
    
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
            (image_id, formatted_path, new_status)
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

def normalize_path(file_path):
    """Convert any path to use forward slashes"""
    return file_path.replace('\\', '/')

def refresh_list():
    """Refresh the master list of all images"""
    global all_images, current_index
    
    image_files = glob.glob(os.path.join(path, 'static', '**', '*.png'), recursive=True)
    image_files = [f.replace('\\', '/') for f in image_files]
    
    random.shuffle(image_files)
    all_images = image_files
    current_index = 0
    
    return all_images

def get_next_batch(batch_size=None):
    """Get next batch of images from the shuffled list"""
    global all_images, current_index
    
    if batch_size is None:
        batch_size = BATCH_SIZE
    
    # Check if we need to refresh the list
    if current_index >= len(all_images):
        refresh_list()
        current_index = 0
    
    # Get the next batch
    end_index = min(current_index + batch_size, len(all_images))
    selected = all_images[current_index:end_index]
    current_index = end_index
    
    # Prepare relative paths for web display
    output_list = []
    for image in selected:
        rel_path = os.path.relpath(image, os.path.join(path, 'static'))
        output_list.append(rel_path.replace('\\', '/'))
    
    return output_list

# Initialize database on startup
init_db()
refresh_list()

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/get_images')
def get_images():
    """Endpoint to get next batch of images with favorite status"""
    start_index = request.args.get('start', 0, type=int)
    batch_size = request.args.get('batch', BATCH_SIZE, type=int)
    
    images = get_next_batch(batch_size)
    
    # Get favorite status for all returned images
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    favorites = {}
    for image_path in images:
        image_id = os.path.basename(image_path)
        cursor.execute('SELECT favorited FROM favorites WHERE image_id = ?', (image_id,))
        result = cursor.fetchone()
        favorites[image_path] = bool(result[0]) if result else False
    
    conn.close()
    
    return jsonify({
        'images': images,
        'favorites': favorites,
        'has_more': current_index < len(all_images)
    })

@app.route('/toggle_favorite', methods=['POST'])
def toggle_favorite_route():
    """Toggle favorite status for an image"""
    data = request.json
    image_path = data.get('image_path')
    if not image_path:
        return jsonify({'error': 'No image path provided'}), 400
    
    abs_path = os.path.join(path, 'static', image_path)
    if not os.path.exists(abs_path):
        return jsonify({'error': 'Image not found'}), 404
    
    new_status = toggle_favorite(abs_path)
    return jsonify({
        'success': True,
        'favorited': new_status,
        'image_path': image_path
    })

@app.route('/delete_image', methods=['POST'])
def delete_image_route():
    """Delete an image"""
    data = request.json
    image_path = data.get('image_path')
    if not image_path:
        return jsonify({'error': 'No image path provided'}), 400
    
    abs_path = os.path.join(path, 'static', image_path)
    if not os.path.exists(abs_path):
        return jsonify({'error': 'Image not found'}), 404
    
    delete_image(abs_path)
    return jsonify({
        'success': True,
        'image_path': image_path
    })

if __name__ == '__main__':
    app.run(debug=True)