"""Extract text from an image using tesseract

Requires python-tesseract

Based on http://code.google.com/p/python-tesseract/wiki/CodeSnippets
"""

import sys
from cv2 import cv
import tesseract


api = tesseract.TessBaseAPI()
api.Init(".", "eng", tesseract.OEM_DEFAULT)
api.SetPageSegMode(tesseract.PSM_AUTO)


def get_text(img):
    tesseract.SetCvImage(img, api)
    text = api.GetUTF8Text()
    return text


def main():
    if len(sys.argv) < 3:
        print "No image file specified"
        print "USAGE: find_obj.py <image>"
        sys.exit(1)

    img = cv.LoadImage("test1.png", cv.CV_LOAD_IMAGE_GRAYSCALE)
    print get_text(img)


if __name__ == "__main__":
    main()
