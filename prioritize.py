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
import PIL.Image
import PIL.ExifTags

# OpenCV
import cv2
import cv2.cv as cv

# Numpy
import numpy

# local
import find_obj
from ocr_text import ocr_text
from detect_skin import detect_skin

###############################################################################
# General tools
###############################################################################


def get_file_list(root, maxfiles=None):
    """Returns a list of up to maxfiles fully-qualified filenames"""
    
    if os.path.isfile(root) and (maxfiles is None or maxfiles > 0):
      return [root]

    all_files = []

    # First get the full listing
    for dirpath, dirnames, filenames in os.walk(root):
        if maxfiles is not None and len(all_files) >= maxfiles:
            break
        for fname in filenames:
            if maxfiles is not None and len(all_files) >= maxfiles:
                break
            all_files.append(os.path.abspath(os.path.join(dirpath, fname)))

    return all_files


def get_hashes(fname):
    """Returns the MD5 and SHA-512 hashes for a file"""
    with open(fname, 'rb') as fh:
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
        print "  DEBUG:", msg

###############################################################################
# Database-related functionality
###############################################################################

# Database filename
DEFAULT_DB_NAME = "prioritize.sqlite"

# Create table statements
CREATE_FILES_TABLE_QUERY = '''CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT,
  filesize INTEGER,
  md5 TEXT,
  sha512 TEXT,
  UNIQUE (sha512)
  )'''

# Create table for JPEG results
CREATE_JPEG_TABLE_QUERY = '''
    CREATE TABLE IF NOT EXISTS jpeg (
        file_id           INTEGER,
        well_formed       BOOLEAN,
        is_solid          BOOLEAN,
        faces             INTEGER,
        screenshot        BOOLEAN, 
        screenshot_fname  TEXT,
        cc                BOOLEAN, 
        cc_fname          TEXT, 
        id                BOOLEAN, 
        id_fname          TEXT,
        contains_skin     BOOLEAN,
        skin_type         TEXT,
        gps_data          TEXT,
        date_data         TEXT,
        model_data        TEXT,
        ocr_text          TEXT
    )'''

# Insert statements

INSERT_FILE_QUERY = '''INSERT INTO files (filename,filesize,md5,sha512) VALUES (?, ?, ?, ?)'''

INSERT_JPEG_QUERY = '''INSERT INTO jpeg
  (file_id, well_formed, is_solid, faces, screenshot, screenshot_fname, cc, cc_fname, 
    id, id_fname, contains_skin, skin_type, gps_data, date_data, model_data, ocr_text)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''

# SELECT
SELECT_SHA512_QUERY = '''SELECT sha512 FROM files WHERE sha512=? LIMIT 1'''
           

def create_db(cursor):
    cursor.execute(CREATE_FILES_TABLE_QUERY)
    cursor.execute(CREATE_JPEG_TABLE_QUERY)


def close_db(conn):
    conn.commit()
    conn.close()


def insert_file_entry(cursor, filename, filesize, md5, sha512):
    cursor.execute(INSERT_FILE_QUERY, (filename, filesize, md5, sha512))
    return cursor.lastrowid


def insert_jpeg_entry(cursor, fileid, well_formed, is_solid, contains_face, screenshot,
      screenshot_fname, is_cc, cc_fname, is_id, id_fname, contains_skin, skin_type, 
      gps_data, date, model, text):
      
    cursor.execute(INSERT_JPEG_QUERY, (fileid, well_formed, is_solid, contains_face, screenshot, 
        str(screenshot_fname).decode('utf-8'), is_cc, str(cc_fname).decode('utf-8'), is_id, 
        str(id_fname).decode('utf-8'), contains_skin, str(skin_type).decode('utf-8'), 
        str(gps_data).decode('utf-8'), 
        str(date).decode('utf-8'), 
        buffer(str(model)), 
        buffer(str(text))))


def find_sha512(cursor, sha512):
  result = cursor.execute(SELECT_SHA512_QUERY, (sha512,))
  return result.fetchone()

  
###############################################################################
# Image processing
###############################################################################

ICON_DIR = "./common_desktop_icons"
CC_DIR = "./cc_images"
ID_DIR = "./id_images"


def init_jpeg(enable_skin, enable_exif, enable_ocr):
    """ Loads in global variables for efficiency purposes"""
    
    # Load in all of the classifiers
    global g_cascades
    g_cascades = load_cascades()
    
    # Load in the icons
    global g_icon
    g_icon = load_imgdir_features(ICON_DIR)  
       
    # Next load in the CC's
    global g_cc
    g_cc = load_imgdir_features(CC_DIR) 
    
    # Next load in the ID's
    global g_id
    g_id = load_imgdir_features(ID_DIR)
    
    # Set the options:
    global g_jpeg_options
    g_jpeg_options = {}
    g_jpeg_options['enable_skin'] = enable_skin
    g_jpeg_options['enable_exif'] = enable_exif
    g_jpeg_options['enable_ocr']  = enable_ocr 


def load_imgdir_features(dirname):
  """Loads all of the features from all images in the dir"""
  result = {}
  for entry in os.listdir(dirname):
    fname = os.path.join(dirname, entry)
    if os.path.isfile(fname):
        try:
            img = load_image(fname)
            detector = cv2.SURF(3200)
            kp, desc = detector.detectAndCompute(img, None)
             
            result[fname] = [img, kp, desc]
        except:
          continue 
  return result   


def load_image(fname):
  img = cv2.imread(fname)
  return img


###############################################################################
# Image Feature Extraction
###############################################################################

def is_well_structured(filename):
  try:
    # First try using PIL, since it's not as noisy:
    img = PIL.Image.open(filename)
    # Then, if that's successful, try it with OpenCV
    img = cv2.imread(filename)
    # It returns None if it fails, instead of raising a useful exception.
    if img is None:
      return False
    else:
      return True
  except:
    return False

def is_solid_color(img):
  """A color is defined as 'mostly solid' if there are less than 3 buckets with
   values > 0 for each color: R,G, and B"""
  
  color = [ (255,0,0),(0,255,0),(0,0,255) ]
  
  for ch,col in enumerate(color):
    # Calculates the histogram
    hist_item = cv2.calcHist([img],[ch],None,[16],[0,16]) 
    # Normalize the value to fall below 255, to fit in image 'h'
    cv2.normalize(hist_item,hist_item,0,255,cv2.NORM_MINMAX) 
    hist=numpy.int32(numpy.around(hist_item))
    
    # Count how many buckets have a value > 0
    cnt = 0
    for arr in hist:
      if arr[0] > 0:
        cnt +=1
      if cnt > 3:
        return False
  return True


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


def within_group(img, group, minmatches=0):
    """\
    Checks if the supplied image is within a group of images.
    The group is represented as a dictionary of filename:image
    
    Note: This is extremely slow and is prone to false positives!
    
    Returns whether or not it matched and the filename ('' if it didn't)
    """
    count = 0
    for fname, details in group.iteritems():
      try:
        small_img, kp, desc = details
        matches = find_obj.match_images(small_img, img, (kp, desc))
        if len(matches) > 0:
          count += 1
        if count > minmatches:
          return True, fname  
      except:
        return False, ''
    return False, ''

def get_skin_type(fname):
    """Gets whether or not there is skin in the image and guesses the type.
    Note: Extremely slow and inaccurate
    
    Future Optimization: Run the image through opencv to find which portions
    are most likely to be a person, and then only examine those portions of
    the image for skin color.
    """
    image = Image.open(fname)
    contains_skin, skin_type = detect_skin(image)
    return contains_skin, skin_type

###############################################################################
# EXIF-specific processing
###############################################################################

def get_exif(fname):
    gps_info = ''
    date_info = ''
    model_info = ''
    try:
        img = PIL.Image.open(fname)
        info = img._getexif()
        for tag, value in info.items():
            tag = PIL.ExifTags.TAGS.get(tag)
            if tag and 'GPSInfo' in tag:
                gps_data = {}
                for gps_tag in value:
                    sub_decoded = PIL.ExifTags.GPSTAGS.get(gps_tag, gps_tag)
                    gps_data[sub_decoded] = value[gps_tag]
                # Now that we have the decoded data data:
                gps_info = str(get_lat_lon(gps_data))                
            elif tag and 'DateTimeOriginal' in tag:
                date_info = str(value)
            elif tag and 'Model' in tag:
                model_info = str(value)
    except:
        pass
    return gps_info, date_info, model_info

def get_lat_lon(gps_info):
    """Returns the latitude and longitude, if available, from the provided GPSInfo exif data"""
    lat = None
    lon = None
		
    gps_latitude = gps_info.get("GPSLatitude")
    gps_latitude_ref = gps_info.get('GPSLatitudeRef')
    gps_longitude = gps_info.get('GPSLongitude')
    gps_longitude_ref = gps_info.get('GPSLongitudeRef')

    if gps_latitude and gps_latitude_ref:
        lat = _convert_to_degress(gps_latitude)
        if gps_latitude_ref != "N":                     
            lat *= -1
    
    if gps_longitude and gps_longitude_ref:
        lon = _convert_to_degress(gps_longitude)
        if gps_longitude_ref != "E":
            lon *= -1

    return lat, lon

def _convert_to_degress(value):
    """Helper function to convert the GPS coordinates stored in the EXIF to degress in float format"""
    deg_num, deg_denom = value[0]
    d = float(deg_num) / float(deg_denom)

    min_num, min_denom = value[1]
    m = float(min_num) / float(min_denom)

    sec_num, sec_denom = value[1]
    s = float(sec_num) / float(sec_denom)

    return d + (m / 60.0) + (s / 3600.0)

###############################################################################
# Tie everything up!
###############################################################################

def process_jpeg(cursor, file_id, fname):
  """Do all of the work required to process a single JPEG"""

  well_structured = False
  is_solid = False
  faces = 0
  is_screenshot, screenshot_fname = False, ''
  is_cc, cc_fname = False, ''
  is_id, id_fname = False, ''
  exif_gps = ''
  exif_date = ''
  exif_model = ''
  contains_skin = ''
  skin_type = ''
  text = ''

  well_structured = is_well_structured(fname)
  if well_structured:
    img = load_image(fname)
    is_solid = is_solid_color(img)
    if not is_solid:
      faces = get_num_faces(img)
      is_screenshot, screenshot_fname = within_group(img, g_icon, 2)
      is_cc, cc_fname = within_group(img, g_cc)
      is_id, id_fname = within_group(img, g_id)
      if (is_cc or is_id) and g_jpeg_options['enable_ocr']:
        text = ocr_text(fname)
      if g_jpeg_options['enable_exif']:
        exif_gps, exif_date, exif_model = get_exif(fname)
      if g_jpeg_options['enable_skin']:
        contains_skin, skin_type = get_skin_type(fname)

  # Mirror the same structure a second time for the debug output
  print_debug("Valid: %s" % str(well_structured))
  if well_structured:
    print_debug("Solid Color: %s" % str(is_solid))
    if not is_solid:
      print_debug("Amount of faces: %d" % faces)
      print_debug("Screenshot? %s: %s" % (str(is_screenshot), screenshot_fname))
      print_debug("CC? %s: %s" % (str(is_cc), cc_fname))
      print_debug("ID? %s: %s" % (str(is_id), id_fname))
      if (is_cc or is_id) and g_jpeg_options['enable_ocr']:
        print_debug("OCRed text: %s" % (str(text)))
        
      if g_jpeg_options['enable_exif']:
        print_debug("GPS Data: %s" % exif_gps)
        print_debug("Date Data: %s" % exif_date)
        print_debug("Model Data: %s" % exif_model)
      if g_jpeg_options['enable_skin']:
        print_debug("Contains skin? %s: Skin Type:%s" % (str(contains_skin), skin_type))

  insert_jpeg_entry(cursor, file_id, well_structured, is_solid, faces, is_screenshot,
                     screenshot_fname, is_cc, cc_fname, is_id, id_fname, contains_skin,
                     skin_type, exif_gps, exif_date, exif_model, text)
  return well_structured

def process_file(cursor, fname):
  """This is the function responsible for tying together all of the other parsing modules"""
  
  # First do the minimal amount we do for every file
  md5, sha512 = get_hashes(fname)
  
  # If it's already in the DB, no processing is necessary
  if find_sha512(cursor, sha512):
    print_debug("It's a duplicate! Skipped!")
    return "duplicate"
  
  size = os.path.getsize(fname)
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
  
  # Disable EXIF data extraction (slow):
  parser.add_argument('--disable_exif', dest='enable_exif', action='store_false',
                      help='Disable EXIF-data extraction (GPS, Model, and Date) (slow)')
  
  # Enable skin checking (slow and inaccurate):
  parser.add_argument('--enable_skin', dest='enable_skin', action='store_true',
                      help='Enable skin-type checking (slow and inaccurate)')
                      
  # Enable text extraction (slow and noisy):
  parser.add_argument('--enable_ocr', dest='enable_ocr', action='store_true',
                      help="Enable text OCRing of ID's and CC's (slow and inaccurate)")


  # Path to examine (required)
  parser.add_argument(dest='path', help='The root directory of the files to examine')
  return parser


def main():
    global g_debug
    # First the initial argument parsing
    parser = build_argparser()
    args = parser.parse_args(sys.argv[1:])

    g_debug     = args.debug
    db_name     = args.db
    maxfiles    = args.maxfiles
    path        = args.path
 
    if maxfiles:
        print_debug("Reading a max of %d files" % maxfiles)
  
    # Initialize stored data used for parsing JPEG files
    init_jpeg(args.enable_skin, args.enable_exif, args.enable_ocr)
  
    # Open a connection to the database and create it if necessary
    if g_debug:
        print "Connecting to DB: '%s'" % db_name
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    create_db(cursor)
  
    start_time = time.time()
  
    # Get the list of JPEG files to process
    files = get_file_list(path, maxfiles)
    print "A list of %d files were retrieved" % len(files)
  
    file_time = time.time() - start_time
  
    statistics = {}
    statistics['valid'] = 0
    statistics['invalid'] = 0
    statistics['duplicates'] = 0
    statistics['total size'] = 0
    statistics['valid size'] = 0
    statistics['processing_time'] = 0
    # Process each of them
    try:
        for i, fname in enumerate(files):
            print "Processing file %d/%d : %s" % (i+1, len(files), fname)
            size = os.path.getsize(fname)
            print_debug('Size: %d bytes' % size)
            statistics['total size'] += size
            result = process_file(cursor, fname)
            if result == "duplicate":
                statistics['duplicates'] += 1
            elif result is True:
                statistics['valid'] += 1
                statistics['valid size'] += size
            elif result is False:
                statistics['invalid'] += 1
            else:
                raise Exception("Unexpected result for %s" % fname)
            # Periodically commit the database results
            if i % 100 == 0:
              conn.commit()
    except Exception, e:
        print "Something bad happened while processing %s!" % fname
        close_db(conn)
        raise
    statistics['processing_time'] = time.time() - file_time - start_time  
    print "*"*80
    print "Statistics"
    if files:
        print "Processed %d files in %0.3f seconds, for an average of %0.3f seconds/file" % (len(files),statistics['processing_time'], statistics['processing_time']/len(files))
        print "A total of %d bytes were processed. %d bytes of valid data" % (statistics['total size'], statistics['valid size'])
        print "%d/%d (%0.3f%%) files were duplicates" % (statistics['duplicates'], len(files), statistics['invalid']*100.0/len(files))
        print "%d/%d (%0.3f%%) files were valid"   % (statistics['valid'], len(files), statistics['valid']*100.0/len(files))
        print "%d/%d (%0.3f%%) files were invalid" % (statistics['invalid'], len(files), statistics['invalid']*100.0/len(files))
    else:
        print "No files processed!"

if __name__ == "__main__":
    main()
