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
#path = 'E:\\Images\\txt2img-images'

# Database setup
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
            favorited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def toggle_favorite(image_path):
    """Toggle favorite status for an image"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    formatted_path = normalize_path(image_path)

    # Extract just the filename or relative path as ID
    image_id = os.path.basename(image_path)
    
    # Check if image exists in favorites
    cursor.execute('SELECT favorited FROM favorites WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    
    if result:
        # Toggle existing entry
        new_status = 0 if result[0] == 1 else 1
        cursor.execute(
            'UPDATE favorites SET favorited = ?, favorited_at = CURRENT_TIMESTAMP WHERE image_id = ?',
            (new_status, image_id)
        )
    else:
        # Insert new entry
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
    # Normalize the path to handle both \ and /
    abs_path = os.path.join(path, 'static', image_path)
    abs_path = os.path.normpath(abs_path)  # Converts to OS-specific format

    # Delete from disk using send2trash
    if os.path.exists(abs_path):
        send2trash(abs_path)

    # Remove from database
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
    global all_images

    # find all images
    #image_files = glob.glob(path+'\\static\\**\*.png', recursive=True)
    image_files = glob.glob(os.path.join(path, 'static', '**', '*.png'), recursive=True)

    # Normalize all paths to use forward slashes
    image_files = [f.replace('\\', '/') for f in image_files]
    
    # Shuffle the list
    random.shuffle(image_files)
    
    # Replace the global list
    all_images = image_files
    
    return all_images


def use_list():
    """Get next 8 images from the shuffled list"""
    global all_images
    
    # Check if we need to refresh the list
    if len(all_images) < 8:
        refresh_list()
    
    # Take the top 8 images (or all if less than 8)
    batch_size = min(8, len(all_images))
    selected = all_images[:batch_size]
    
    # Remove selected images from the global list
    all_images = all_images[batch_size:]
    
    # Prepare relative paths for web display
    output_list = []
    for image in selected:
        # Get relative path from static folder
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
    images = use_list()
    
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
        'favorites': favorites
    })

@app.route('/toggle_favorite', methods=['POST'])
def toggle_favorite_route():
    """Toggle favorite status for an image"""
    data = request.json
    image_path = data.get('image_path')
    if not image_path:
        return jsonify({'error': 'No image path provided'}), 400
    
    # Convert relative path to absolute path
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
    
    # Convert relative path to absolute path
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