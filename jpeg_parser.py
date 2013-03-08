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

Well-formed / number of faces / possible screenshot (contains a known icon) / normal distribution of colors (or perhaps some number) / EXIF data / common EXIF fields


"""

# built-ins
import os
import sys
import time
import hashlib
import os.path
import sqlite3
import argparse


# PIL
import Image

# OpenCV
import cv2
import cv2.cv as cv

# local
import find_obj

###############################################################################
# General tools
###############################################################################

def get_file_list(rootdir, maxfiles=None):
  """Returns a list of up to maxfiles fully-qualified filenames"""
  all_files = []
  
  # First get the full listing
  for dirpath, dirnames, filenames in os.walk(rootdir):
    if maxfiles is not None and len(all_files) >= maxfiles:
        break
    for fname in filenames:
      if maxfiles is not None and len(all_files) >= maxfiles:
        break
      all_files.append(os.path.abspath( os.path.join(dirpath, fname) ))
         
    
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
  
  
def print_debug(msg):
  if g_debug:
    print msg

###############################################################################
# Database-related functionality
###############################################################################

# Database filename
DEFAULT_DB_NAME = "prioritize_data.sqlite"

# Create table statements
CREATE_FILES_TABLE_QUERY = '''CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT,
  filesize INTEGER,
  md5 TEXT,
  sha512 TEXT
  )'''

# Create table for JPEG results
CREATE_JPEG_TABLE_QUERY = '''
  CREATE TABLE IF NOT EXISTS jpeg (
    file_id INTEGER,
    well_formed BOOLEAN,
    faces INTEGER,
    screenshot BOOLEAN, 
    screenshot_fname TEXT
  )'''

# Insert statements

INSERT_FILE_QUERY = '''INSERT INTO files (filename,filesize,md5,sha512) VALUES (?, ?, ?, ?)'''

INSERT_JPEG_QUERY = '''INSERT INTO jpeg
  (file_id, well_formed, faces, screenshot, screenshot_fname) VALUES (?, ?, ?, ?, ?)'''

# SELECT
SELECT_SHA512_QUERY = '''SELECT sha512 FROM files WHERE sha512=? LIMIT 1'''
           
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
  
def insert_jpeg_entry(cursor, fileid, well_formed, contains_face, screenshot, screenshot_fname):
  cursor.execute(INSERT_JPEG_QUERY, (fileid, well_formed, contains_face, screenshot, screenshot_fname))

def find_sha512(cursor, sha512):
  result = cursor.execute(SELECT_SHA512_QUERY, (sha512,))
  return result.fetchone()
  
###############################################################################
# Image processing
###############################################################################

ICON_DIR = "./common_desktop_icons"

def init_jpeg():
    """ Loads in global variables for efficiency purposes"""
    global g_cascades
    global g_icons
    global g_icon_names
    
    # Load in all of the classifiers
    g_cascades = load_cascades()
    
    fnames = []
    dirs = []
    for entry in os.listdir(ICON_DIR):
        entry = os.path.join(ICON_DIR, entry)
        if os.path.isdir(entry):
            dirs.append(entry)
        elif os.path.isfile(entry):
            fnames.append(entry)
        else:
            print fnames, dirs
            raise Exception("What is '%s'?" % entry)
    
    g_icons = {}
    g_icon_names = {}
    # Load in all of the desktop icons:
    # First the 'general' icons
    g_icons['general'] = []
    g_icon_names['general'] = []
    
    for fname in fnames:
        icon = cv2.imread(fname, 0)
        g_icons['general'].append(icon)
        g_icon_names['general'].append(fname)
    
    # Then the OS-specific ones
    for dir_name in dirs:
        g_icons[dir_name] = []
        g_icon_names[dir_name] = []
        for fname in os.listdir(dir_name):
            icon = cv2.imread(os.path.join(dir_name,fname), 0)
            g_icons[dir_name].append(icon)
            g_icon_names[dir_name].append(fname)

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

  
def get_num_faces(img):
  """\
  Magic from https://github.com/Itseez/opencv/blob/master/samples/python2/facedetect.py
  Takes a file loaded with cv2.imread(fname) and runs a haarcascade through it.
  If it detects anything, we're good!
  """
  gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  gray = cv2.equalizeHist(gray)

  max_faces = 0
  # Returns the largest amount of faces matched by a single cascade

  for cascade in g_cascades:
    rects = cascade.detectMultiScale(img, scaleFactor=1.3, minNeighbors=4, minSize=(30, 30), flags = cv.CV_HAAR_SCALE_IMAGE)
    max_faces = max(max_faces, len(rects))    
  return max_faces

#def contains_flesh():
#  pass
    

def is_screenshot(img):
    """\
    Checks if the supplied image is likely to be a screenshot.
    
    This check is done by searching for a series of common icons.
    Additionally, it will attempt to make a guess about the OS based on the
    amount of matches of OS-specific images.
    
    Note: This is extremely slow and is prone to false positives!
    """

    total = 0
    results = {}
    matched = False
    fname = ''
    for group, icons in g_icons.iteritems():
      results[group] = 0
      for i, icon in enumerate(icons):
        try:
          matches = find_obj.match_images(icon, img)
        except:
          return False, fname
        
        if len(matches) > 0:
          fname = "%s/%s" % (group, g_icon_names[group][i] )
          #print_debug("Matched as being %s/%s" % (group, g_icon_names[group][i] ))
          results[group] += 1
          matched = True
          break
      if matched:
        break
      
    # Now that we have results, let's examine them:
    total = sum(results.itervalues())
    return total > 0, fname
    

def process_jpeg(cursor, file_id, fname):
  """Do all of the work required to process a single JPEG"""

  well_structured = False
  faces = 0
  screenshot= False
  screenshot_fname = ''

  well_structured = is_well_structured(fname)
  if well_structured:
    img = load_image(fname)
    faces = get_num_faces(img)
    screenshot, screenshot_fname = is_screenshot(img)

  if g_debug:
    print "Valid: %s, faces: %d, screenshot: %s, screenshot file: %s" % (str(well_structured), faces, str(screenshot), screenshot_fname)

  insert_jpeg_entry(cursor, file_id, well_structured, faces, screenshot, screenshot_fname)
  return well_structured
  

###############################################################################
# Tie everything up!
###############################################################################

def process_file(cursor, fname):
  """This is the function responsible for tying together all of the other parsing modules"""
  
  # First do the minimal amount we do for every file
  md5, sha512 = get_hashes(fname)
  size = os.path.getsize(fname)
  
  # If it's already in the DB, no processing is necessary
  if find_sha512(cursor, sha512):
    if g_debug:
      print "It's a duplicate! Skipped!"
    return "duplicate"
  
  file_id = insert_file_entry(cursor, fname, size, md5, sha512)

  # Then handle the remaining modules  
  valid = process_jpeg(cursor, file_id, fname)
  return valid
  
def build_argparser():
  parser = argparse.ArgumentParser(description='Extracts features for prioritizing recovered data')
  # g_debug mode
  parser.add_argument('--debug', dest='debug', action='store_true',
                      help='Add additional logging data')
  
  # DB filename  
  parser.add_argument('--db', dest='db', action='store',
                      default=DEFAULT_DB_NAME,
                      help='Override the default filename used for the database (default is %s)' % DEFAULT_DB_NAME)
  # maxfiles     
  parser.add_argument('--maxfiles', dest='maxfiles', action='store', type=int,
                      default=None,
                      help='Specify an upper limit to the amount of files that are examined')
             
  # Path to examine (required)
  parser.add_argument(dest='path', help='The root directory of the files to examine')
  return parser

def main():
  global g_debug
  # First the initial argument parsing
  parser = build_argparser()
  args = parser.parse_args(sys.argv[1:])
  
  g_debug   = args.debug
  db_name   = args.db
  maxfiles  = args.maxfiles
  path      = args.path
  
  if maxfiles:
    print_debug("Reading a max of %d files" % maxfiles)
  
  # Initialize stored data used for parsing JPEG files
  init_jpeg()
  
  # Open a connection to the database and create it if necessary
  if g_debug:
    print "Connecting to DB: '%s'" % db_name
  conn = sqlite3.connect(db_name)
  cursor = conn.cursor()
  create_db(cursor)
  
  start_time = time.time()
  
  # Get the list of JPEG files to process
  files = get_file_list(path, maxfiles)
  if g_debug:
    print "A list of %d files were retrieved" % len(files)
  
  file_time = time.time() - start_time
  
  statistics = {}
  statistics['valid'] = 0
  statistics['invalid'] = 0
  statistics['duplicates']   = 0
  # Process each of them
  for i, fname in enumerate(files):
    if g_debug:
      print "Processing file %d/%d : %s" % (i+1, len(files), fname)
    result = process_file(cursor, fname)
    if result == "duplicate":
      statistics['duplicates'] += 1
    elif result is True:
      statistics['valid'] += 1
    elif result is False:
      statistics['invalid'] += 1
    else:
      raise Exception("Unexpected result for %s" % fname)

  processing_time = time.time() - file_time - start_time  
  
  close_db(conn)

  print "*"*80
  print "Statistics"
  if files:
    print "Processed %d files in %0.3f seconds, for an average of %0.3f seconds/file" % (len(files),processing_time, processing_time/len(files))
    
    print "%d/%d (%0.3f%%) files were duplicates" % (statistics['duplicates'], len(files), statistics['invalid']*100.0/len(files))
    print "%d/%d (%0.3f%%) files were valid"   % (statistics['valid'], len(files), statistics['valid']*100.0/len(files))
    print "%d/%d (%0.3f%%) files were invalid" % (statistics['invalid'], len(files), statistics['invalid']*100.0/len(files))
  else:
    print "No files processed!"

if __name__ =="__main__":
  main()
