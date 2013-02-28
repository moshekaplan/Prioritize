Prioritize-Data
===============

Takes files obtained by file-carving and extracts features from them to help prioritize "interesting" files.

One of the problems in digital forensics is dealing with the sheer amount of data that can be acquired from a system. The purpose of this project is to determine which files would likely be of most interest for a forensic investigator. A file is considered to be interesting if it has features that are characteristic of files that are useful during an investigation.

All of the collected data will be stored in a SQLite database for easy access afterwards. In order to facilitate the use of the collected data, there will also be a script that will extract either a controlled amount or percentage of the "most interesting" files to a location.


This program will initially only support image files. For an image file, the following data is considered interesting:
 * Screenshots of a user's desktop
 * Pictures of people
 * Pictures of credit cards
 * EXIF location, date, and camera model information

As such, the following features will be extracted:
 *	Removing 'useless' images:
   *	Check if the image is well-structured, and can be opened in a normal image viewer. If it is not, there is no point in examining it further.
   *	Check the variation of the colors within the image, to rule out images that are a solid color
 *	Data collection:
   *	The number of faces within the image
   *	If the image looks like it may be a screen capture (based on the presence of artifacts that are usually on a desktop, like a start menu, or icons for well-known programs)
   *	If the image contains a credit card
   *  If the image contains something that looks like a photo ID
   *	The presence of EXIF data, and specific EXIF fields (GPS, date, and camera model)
