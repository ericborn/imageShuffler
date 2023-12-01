import os
import glob
import random
from flask import Flask, render_template

app = Flask(__name__)

path = os.path.dirname(os.path.realpath(__file__))

# TODO
# store previous 8 images and shuffle until those 8 do not appear in the next
# store a list of previous images for x generations and shuffle until they do not appear in the next
# the shuffle function could be on a seperate time from the app router so it has time to prepare
# the images during the refresh delay

# 2 lists, one used one not. on load move images into used and refresh to check for new files to put into not used. Load 8 from not used.
# once a threshold of not used is reached, ie. less than 8 images remaining, reset the used list.


def create_shuffle_list():
    result_list = []
    items_per_sublist = 8

    all_images = [os.path.basename(image) for image in glob.glob(path+'\\static\\*.png')]

    for image in range(24):
        selected_items = random.sample(all_images, items_per_sublist)
        result_list.append(selected_items)

    return(result_list)


def revise_shuffle_list(original_list):
    if len(original_list) == 0:
        original_list = create_shuffle_list()
        print("revise shuffle result")
        return(original_list)
    
    else:
        original_list.pop(0)
        print("revise shuffle original")
        return(original_list)

image_list = create_shuffle_list()

@app.route('/')
def index():
    return render_template('index.html', image_list=image_list[0])

# route called from JS which shuffles
@app.route('/get_images')
def get_images():
    result_list = revise_shuffle_list(image_list)
    return (result_list[0])

if __name__ == '__main__':
    app.run(debug=True)