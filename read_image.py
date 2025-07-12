'''
given an image of FlyWheel Studio studio bike
Read information like torque and speed from it.
'''
import numpy as np
from PIL import Image
import cv2
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

from matplotlib import pyplot as plt

def preprocess_image(image):
    '''
    
    '''
    # show raw image
    #img.show()

    # get blue channel of the image
    # TODO: cluster pixels based on color, find out the color of the blue pixel, only pick pixels of that color
    blue_channel = image.split()[2]
    #blue_channel.show()
    return blue_channel

def crop_torque_and_cadence_imgs(full_image):
    # get a subimage of the torque and cadence values
    torque_img = full_image[1200:1800, 0:1200] # extract torque image
    cadence_img = full_image[1200:1800, 1200:2200] # extract cadence image
    return (torque_img, cadence_img)


def img_to_int(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (70, 60, 80), (100, 255, 255))  # isolate cyan pixels
    gray = cv2.bitwise_and(hsv[:,:,2], hsv[:,:,2], mask=mask)  # take V channel
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]

    config = ("--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789") # treat the image as a single text line.
    text = pytesseract.image_to_string(thresh, config=config)
    return int(text)

def get_torque_and_cadence_from_image(image):
    '''
    '''
    torque_img, cadence_img = crop_torque_and_cadence_imgs(img)
    torque = img_to_int(torque_img)
    cadence = img_to_int(cadence_img)
    return (torque, cadence)

if __name__ == "__main__":
    # load test image from disk for testing

    img = cv2.imread("test_image_1.jpg")
    torque, cadence = get_torque_and_cadence_from_image(img)
    print(f"Torque: {torque} percent")
    print(f"Cadence: {cadence} RPM")
