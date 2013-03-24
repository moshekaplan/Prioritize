"""
Utility for examining data extracted from images.

Creates an HTML file that displays all of the images.
"""

import sys
import sqlite3
import argparse

g_debug = False

###############################################################################
# Database-related functionality
###############################################################################
def open_db(db_name):
    if g_debug:
        print "Connecting to DB: '%s'" % db_name
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    return cursor


def get_query_results(cursor, query):
    cursor.execute(query)
    query_results = cursor.fetchall()
    results = []
    fields = "filename, faces, screenshot, screenshot_fname, cc, cc_fname, jpeg.id, id_fname, contains_skin, skin_type, gps_data".split(', ')
    for result in query_results:
        results.append(dict(zip(fields, result)))
    return results


def order_by_faces(cursor, maxfiles=None):
    query = '''SELECT files.filename, faces, screenshot, screenshot_fname, cc, cc_fname, jpeg.id, id_fname, contains_skin, skin_type, gps_data
    FROM jpeg JOIN files
        ON files.id = jpeg.file_id
    WHERE well_formed = 1 AND is_solid = 0
    ORDER BY faces DESC
    '''

    if maxfiles:
        query += " LIMIT %d" % maxfiles

    return get_query_results(cursor, query)

def order_by_cc(cursor, maxfiles=None):
    query = '''SELECT files.filename, faces, screenshot, screenshot_fname, cc, cc_fname, jpeg.id, id_fname, contains_skin, skin_type, gps_data
    FROM jpeg JOIN files
        ON files.id = jpeg.file_id
    WHERE well_formed = 1 
    ORDER BY cc DESC
    '''

    if maxfiles:
        query += " LIMIT %d" % maxfiles

    return get_query_results(cursor, query)

def order_by_id(cursor, maxfiles=None):
    query = '''SELECT files.filename, faces, screenshot, screenshot_fname, cc, cc_fname, jpeg.id, id_fname, contains_skin, skin_type, gps_data
    FROM jpeg JOIN files
        ON files.id = jpeg.file_id
    WHERE well_formed = 1 
    ORDER BY jpeg.id DESC
    '''

    if maxfiles:
        query += " LIMIT %d" % maxfiles

    return get_query_results(cursor, query)

###############################################################################
# File-related functionality
###############################################################################

HTML_HEADER = """<html>
<head>
    <META http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <STYLE type="text/css">
    img {
    max-height: 640px;
    max-width:  640px;
    padding: 20px;
    }
    </STYLE>
</head>
<body><center>"""

HTML_FOOTER = """</center></body></html> """

def write_file(fname, imagesinfo):
    """This function will write the output to a file
    imagesinfo is a list of dictionaries, where each entry is the information
    for an image
    """

    #    filename, faces, screenshot, screenshot_fname, cc, cc_fname, jpeg.id, id_fname, contains_skin, skin_type, gps_data
    with open(fname,'w') as fh:    
        fh.write(HTML_HEADER)
        for entry in imagesinfo:
            fh.write('<img src="%s"></><br/>\n' % entry['filename'])
            fh.write("<table>")
            fh.write("<tr><td>Filename:</td> <td>%s</td><br/>" % entry['filename'])
            fh.write("<tr><td>GPS Data:</td> <td>%s</td><br/>" % entry['gps_data'])
            fh.write("</table><hr>\n\n")
        fh.write(HTML_FOOTER)

###############################################################################
# General functionality
###############################################################################

DEFAULT_DB_NAME     = "prioritize.sqlite"
DEFAULT_OUTPUT_NAME = "prioritize.html"

def build_argparser():
    parser = argparse.ArgumentParser(description='Extracts data from the sqlite DB')
    
    parser.add_argument('--debug', dest='debug', action='store_true',
                      help='Add additional logging data')

    parser.add_argument('--db', dest='db', action='store',
                      default=DEFAULT_DB_NAME,
                      help='Override the default source database (default is %s)' % DEFAULT_DB_NAME)

    parser.add_argument('--maxfiles', dest='maxfiles', action='store', type=int,
                      default=100,
                      help='Specify an upper limit to the amount of files that will be returned. Defaults to the top 100')

    parser.add_argument('--output', dest='output', action='store',
                      default=DEFAULT_OUTPUT_NAME,
                      help='Override the default destination filename (default is %s)' % DEFAULT_OUTPUT_NAME)
    return parser


def main():
    global g_debug
    # First the initial argument parsing
    parser = build_argparser()
    args = parser.parse_args(sys.argv[1:])

    g_debug    = args.debug
    db_name    = args.db
    maxfiles   = args.maxfiles
    output     = args.output
    
    # Open a connection to the database    
    cursor = open_db(db_name)

    results = order_by_faces(cursor, maxfiles)
    #for result in results:
        #print result

    write_file(output, results)
    print "Open %s to see the results" % output

if __name__ == "__main__":
    main()

# useful queries for now:

# Faces are most important


