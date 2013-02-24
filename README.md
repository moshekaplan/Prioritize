Prioritize-Data
===============

Takes files obtained by file-carving and extracts features from them to help prioritize "interesting" files.

One of the problems related to forensics is dealing with the sheer amount of data that can be retrieved from a system. The purpose of this project is to determine which files would likely be the most interesting for an investigator. This will be done by extracting features that would be deemed relevant for an investigation.

As a proof of concept, it will contain a module for determining which JPEG images are interesting. This will be done by checking the structure of the image, the variation of colors within the image, if the image contains EXIF data, if the image contains a person's face, and if there is reason to believe that the image contains a screenshot of a person's desktop.
