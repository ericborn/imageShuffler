# -*- coding: utf-8 -*-
"""
Created on Thu Dec  7 14:53:54 2023

@author: eric
"""

import os
import glob
import random
from flask import Flask, render_template

app = Flask(__name__)

path = os.path.dirname(os.path.realpath(__file__))

#path = 'C:\\stable-diffusion-webui-1.6.0\\outputs\\txt2img-images'

# TODO
# store previous 8 images and shuffle until those 8 do not appear in the next
# store a list of previous images for x generations and shuffle until they do not appear in the next
# the shuffle function could be on a seperate time from the app router so it has time to prepare
# the images during the refresh delay

# 2 lists, one used one not. on load move images into used and refresh to check for new files to put into not used. Load 8 from not used.
# once a threshold of not used is reached, ie. less than 8 images remaining, reset the used list.

def refresh_list(used_list):
    # find all images
    all_images = glob.glob(path+'\\static\\**\*.png', recursive=True)
   
    # remove images already used
    unused_images = [i for i in all_images if i not in used_list]
    
    # reset used_list if there are less than 20 unused images left
    if len(unused_images) < 20:
        used_list = []
        unused_images = [i for i in all_images if i not in used_list]
    
    return(unused_images)

def use_list(input_list):
    global used_list
    random.shuffle(input_list)
    used_list += input_list[0:8]
    output_list = []
    for image in range(8):
        output_list.append(input_list[image][61:]) 
    return(output_list[0:8])

used_list = []

@app.route('/')
def index():
    # global original_list
    use_list(refresh_list(used_list))
    return render_template('index.html', image_list=use_list(refresh_list(used_list))) #image_list=image_list[0])

# route called from JS which shuffles
@app.route('/get_images')
def get_images():
    # global original_list
    # manage_shuffle_list()
    return (use_list(refresh_list(used_list)))

if __name__ == '__main__':
    app.run(debug=True)