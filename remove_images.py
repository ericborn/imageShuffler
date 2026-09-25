import sqlite3
import os
from image_utils import delete_image


image_path = 'E:/imageShuffler'
os.chdir(image_path)
print("After:", os.getcwd())

conn = sqlite3.connect('image_evaluations.db')
cursor = conn.cursor()
cursor.execute("SELECT file_path FROM image_details WHERE verdict != 'Keeper'")

rows = cursor.fetchall()

for row in rows:
    #print(row[0])
    delete_image(row[0])
conn.close()