import os
import glob
import random
from flask import Flask, render_template

app = Flask(__name__)

path = os.path.dirname(os.path.realpath(__file__))

images = []

# TODO
# store previous 8 images and shuffle until those 8 do not appear in the next
# store a list of previous images for x generations and shuffle until they do not appear in the next
# the shuffle function could be on a seperate time from the app router so it has time to prepare
# the images during the refresh delay
def gather_shuffle_images():
    images = [os.path.basename(image) for image in glob.glob(path+'\\static\\*.png')]
    random.shuffle(images)
    return(images[0:8])

@app.route('/')
def index():
    return render_template('index.html', image_list=images[0:8])

# route called from JS which shuffles
@app.route('/get_images')
def get_images():
    #random.shuffle(images)
    return (gather_shuffle_images())

if __name__ == '__main__':
    app.run(debug=True)