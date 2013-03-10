"""\
Detects the presence of skin (and the color) within an image.

Based on http://www.linux-magazin.de/Ausgaben/2011/07/Objekterkennung/%28offset%29/2&usg=ALkJrhhRkuCGbrUtuAT3ybPqIHnIOxR-Mg#article_l2

Note: Extremely slow and inaccurate.
"""

import sys
from collections import Counter

from PIL import Image

gSkinThreshold = 10

def detect_skin(image):
  """Examines each pixel for whether or not it's within the range of colors associated with skin"""
  
  lImageW = image.size[0]
  lImageH = image.size[1]
  
  counter = Counter()
  
  if (image.mode == "RGB"):
    for lY in range(0, lImageH):
      for lX in range(0, lImageW):
        lXY = (lX, lY)
        lRGB = image.getpixel(lXY)
        if ( ((lRGB[0] > 225) and (lRGB[0] < 255)) and ((lRGB[1] > 170) and (lRGB[1] < 230)) and ((lRGB[2] > 180) and (lRGB[2] < 235))):
          counter['light caucasian'] += 1
        elif ( ((lRGB[0] > 220) and (lRGB[0] < 255)) and ((lRGB[1] > 150) and (lRGB[1] < 210)) and ((lRGB[2] > 145) and (lRGB[2] < 200))):
          counter['caucasian'] += 1
        elif ( ((lRGB[0] > 190) and (lRGB[0] < 235)) and ((lRGB[1] > 100) and (lRGB[1] < 150)) and ((lRGB[2] > 90) and (lRGB[2] < 125))):
          counter['dark caucasian'] += 1
        elif ( ((lRGB[0] > 215) and (lRGB[0] < 255)) and ((lRGB[1] > 150) and (lRGB[1] < 200)) and ((lRGB[2] > 110) and (lRGB[2] < 155))):
          counter['asian'] += 1
        elif ( ((lRGB[0] > 170) and (lRGB[0] < 220)) and ((lRGB[1] > 85) and (lRGB[1] < 135)) and ((lRGB[2] > 50) and (lRGB[2] < 100))):
          counter['light african'] += 1
        elif ( ((lRGB[0] > 45) and (lRGB[0] < 95)) and ((lRGB[1] > 20) and (lRGB[1] < 65)) and ((lRGB[2] > 5) and (lRGB[2] < 60))):
          counter['dark african'] += 1

  percent_skin = 100.0*sum(counter.itervalues())/(lImageW*lImageH)
  if percent_skin > gSkinThreshold:
    most_common = counter.most_common(1) 
    # At least 50% of a single color
    if most_common and 1.0*most_common[0][1]/sum(counter.itervalues()) > 0.5:
      return True, most_common[0][0]
    else:
      return True, "Unknown"
  else:
    return False, ""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "No filename specified"
        print "USAGE: detect_skin.py <filename>"
        sys.exit(1)

    image = Image.open(sys.argv[1])
    print detectSkin(image)
