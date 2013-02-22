"""
Given a list of JPEG files:

Extract features from each.
At a minimum, if it has a valid structure, path, file size, EXIF data, md5, sha1, sha2
Additionally, containing flesh tones, and possibly flesh colors, and color variety (more = more useful) would be nice.

This data would all be stored in a SQLite database

Write some scripts for prioritizing files based on some combination of these features

First table:

ID / Path / File Size / MD5 / SHA2-512 / Well-formed / 

"""

import os
import hashlib
import os.path


# PIL
import Image

# OpenCV
import cv2
import cv2.cv as cv


###############################################################################
# General tools
###############################################################################

def get_file_list(rootdir, maxfiles=None):
  """Returns a list of up to maxfiles fully-qualified filenames"""
  all_files = []
  
  # First get the full listing
  for dirpath, dirnames, filenames in os.walk(rootdir):
    # add up to maxfiles files
    for fname in filenames:
      all_files.append(os.path.abspath( os.path.join(dirpath, fname) ))
      if maxfiles is not None and len(all_files) >= maxfiles:
        break     
    
  return all_files

def get_hashes(fname):
  """Returns the MD5 and SHA-512 hashes for a file"""
  pass
  

###############################################################################
# Database
###############################################################################

def create_db():
  pass


###############################################################################
# Image processing
###############################################################################

def load_image(fname):
  img = cv2.imread(fname)
  return img

def load_cascade(fname):
  """Given a filename, returns the loaded cascade"""
  cascade = cv2.CascadeClassifier(fname)
  return cascade

def is_well_structured(filename):
  try:
    # First try using PIL, since it's not as noisy:
    img = Image.open(filename)
    # Then, if that's successful, try it with OpenCV
    img = cv2.imread(filename)
    # It returns None if it fails, instead of raising a useful exception.
    if img is None:
      return False
    else:
      return True
  except:
    return False

  
def contains_face(img, cascade):
  """\
  Magic from https://github.com/Itseez/opencv/blob/master/samples/python2/facedetect.py
  Takes a file loaded with cv2.imread(fname) and runs a cascade through it.
  If it detects anything, we're good!
  """
  gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  gray = cv2.equalizeHist(gray)
  rects = cascade.detectMultiScale(img, scaleFactor=1.3, minNeighbors=4, minSize=(30, 30), flags = cv.CV_HAAR_SCALE_IMAGE)
  if len(rects):
    return True
  else:
    return False

def contains_flesh():
  pass


###############################################################################
# Tie everything up!
###############################################################################


if __name__ =="__main__":
  cascade_fn = "./haarcascades/haarcascade_frontalface_alt2.xml"
  cascade = load_cascade(cascade_fn)  
    
  files = get_file_list('.')
  for fname in files:
    well_structured = is_well_structured(fname)
    if well_structured:
      img = load_image(fname)
      face = contains_face(img, cascade)
      if face:
        print fname, is_well_structured(fname), face
