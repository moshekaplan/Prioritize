"""
Given a list of JPEG files:

Extract features from each.
At a minimum, if it has a valid structure, path, file size, EXIF data, md5, sha1, sha2
Additionally, containing flesh tones, and possibly flesh colors, and color variety (more = more useful) would be nice.

This data would all be stored in a SQLite database

Write some scripts for prioritizing files based on some combination of these features

First table:

ID / Path / File Size / MD5 / SHA2-512

JPEG Table:

Well-formed / contains face / possible screenshot (contains a known icon) / normal distribution of colors (or perhaps some number) / EXIF data / common EXIF fields


"""

import os
import sys
import time
import hashlib
import os.path
import sqlite3


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
  with open(fname,'rb') as fh:
    data = fh.read()
    md5 = hashlib.md5(data).hexdigest()
    sha512 = hashlib.sha512(data).hexdigest()
    return md5, sha512
  
def load_cascades():
  fnames = ['./haarcascades/haarcascade_frontalface_alt.xml',
            './haarcascades/haarcascade_frontalface_alt2.xml']
  
  cascades= []
  
  for cascade_fn in fnames:
    if os.path.exists(cascade_fn) and os.path.isfile(cascade_fn):
      cascade = cv2.CascadeClassifier(cascade_fn)
      cascades.append(cascade)
  if not cascades:
    print "Failed to load any classifier!"
    sys.exit(1)
  
  return cascades
  
###############################################################################
# Database-related functionality
###############################################################################

# Database filename
DB_NAME = "prioritize_data.sqlite"

# Create table statements
CREATE_FILES_TABLE_QUERY = '''CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT,
  filesize INTEGER,
  md5 TEXT,
  sha512 TEXT
  )'''

# Create table for JPEG results
CREATE_JPEG_TABLE_QUERY = '''CREATE TABLE IF NOT EXISTS jpeg (
  file_id INTEGER,
  well_formed BOOLEAN,
  contains_face BOOLEAN
  )'''

# Insert statements

INSERT_FILE_QUERY = '''INSERT INTO files (filename,filesize,md5,sha512) VALUES (?, ?, ?, ?)'''

INSERT_JPEG_QUERY = '''INSERT INTO jpeg
  (file_id, well_formed, contains_face) VALUES (?, ?, ?)'''
           
def create_db(cursor):
  cursor.execute(CREATE_FILES_TABLE_QUERY)
  cursor.execute(CREATE_JPEG_TABLE_QUERY)
  pass

def close_db(conn):
  conn.commit()
  conn.close()

def insert_file_entry(cursor, filename, filesize, md5, sha512):
  cursor.execute(INSERT_FILE_QUERY, (filename, filesize, md5, sha512))
  return cursor.lastrowid
  
def insert_jpeg_entry(cursor, fileid, well_formed, contains_face):
  cursor.execute(INSERT_JPEG_QUERY, (fileid, well_formed, contains_face))

  
###############################################################################
# Image processing
###############################################################################

def load_image(fname):
  img = cv2.imread(fname)
  return img

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

  
def has_face(img, cascades):
  """\
  Magic from https://github.com/Itseez/opencv/blob/master/samples/python2/facedetect.py
  Takes a file loaded with cv2.imread(fname) and runs a cascade through it.
  If it detects anything, we're good!
  """
  gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  gray = cv2.equalizeHist(gray)
  # Returns True if a single cascade matches
  for cascade in cascades:
    rects = cascade.detectMultiScale(img, scaleFactor=1.3, minNeighbors=4, minSize=(30, 30), flags = cv.CV_HAAR_SCALE_IMAGE)
    if len(rects):
      return True
  return False

def contains_flesh():
  pass


def process_jpeg(cascades, cursor, file_id, fname):
  """Do all of the work required to process a single JPEG"""

  well_structured = False
  contains_face = False

  well_structured = is_well_structured(fname)
  if well_structured:
    img = load_image(fname)
    contains_face = has_face(img, cascades)
  
  insert_jpeg_entry(cursor, file_id, well_structured, contains_face)
  

###############################################################################
# Tie everything up!
###############################################################################

def process_file(cascades, cursor, fname):
  """This is the function responsible for tying together all of the other parsing modules"""
  
  # First do the minimal amount we do for every file
  md5, sha512 = get_hashes(fname)
  size = os.path.getsize(fname)
  file_id = insert_file_entry(cursor, fname, size, md5, sha512)

  # Then handle the remaining modules  
  process_jpeg(cascades, cursor, file_id, fname)
  

def main():

  # Load up the classifiers
  cascades = load_cascades()
  
  # Open a connection to the database and create it if necessary
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  create_db(cursor)
  
  start_time = time.time()
  
  # Get the list of JPEG files to process
  files = get_file_list('/media/1.5TB/40_gb')
  
  file_time = time.time() - start_time
  
  # Process each of them
  for fname in files:
    result = process_file(cascades, cursor, fname)

  processing_time = time.time() - file_time - start_time  
  
  close_db(conn)

  if files:
    print "Processed %d files in %0.3f seconds, for an average of %0.3f seconds/file" % (len(files),processing_time, processing_time/len(files))
  else:
    print "No files processed!"

if __name__ =="__main__":
  main()
