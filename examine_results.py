"""
Utility for examining data extracted from images.

Creates an HTML file that displays all of the images.
"""

import sys
import sqlite3
import argparse

g_debug = False


###############################################################################
# Generic helpers
###############################################################################

def print_debug(msg):
    if g_debug:
        print "  DEBUG:", msg
        
###############################################################################
# Database-related functionality
###############################################################################
def open_db(db_name):
    print_debug("Connecting to DB: '%s'" % db_name)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    return cursor


def get_query_results(cursor, query):
    cursor.execute(query)
    query_results = cursor.fetchall()
    results = []
    fields = "filename, faces, screenshot, screenshot_fname, cc, cc_fname, jpeg.id, id_fname, contains_skin, skin_type, gps_data, date_data, model_data, ocr_text".split(', ')
    for result in query_results:
        results.append(dict(zip(fields, result)))
    return results


def order_by_faces(cursor, maxfiles=None):
    print_debug('Prioritizing by the number of faces')

    query = '''SELECT files.filename, faces, screenshot, screenshot_fname, cc, cc_fname, 
                jpeg.id, id_fname, contains_skin, skin_type, gps_data, date_data, model_data, ocr_text
    FROM jpeg JOIN files
        ON files.id = jpeg.file_id
    WHERE well_formed = 1 AND is_solid = 0
    ORDER BY faces DESC
    '''

    if maxfiles:
        query += " LIMIT %d" % maxfiles

    return get_query_results(cursor, query)

def order_by_cc(cursor, maxfiles=None):
    query = '''SELECT files.filename, faces, screenshot, screenshot_fname, cc, cc_fname, 
                jpeg.id, id_fname, contains_skin, skin_type, gps_data, date_data, model_data, ocr_text
    FROM jpeg JOIN files
        ON files.id = jpeg.file_id
    WHERE well_formed = 1 
    ORDER BY cc DESC
    '''

    if maxfiles:
        query += " LIMIT %d" % maxfiles

    return get_query_results(cursor, query)

def order_by_id(cursor, maxfiles=None):
    query = '''SELECT files.filename, faces, screenshot, screenshot_fname, cc, cc_fname, 
                jpeg.id, id_fname, contains_skin, skin_type, gps_data, date_data, model_data, ocr_text
    FROM jpeg JOIN files
        ON files.id = jpeg.file_id
    WHERE well_formed = 1 
    ORDER BY jpeg.id DESC
    '''

    if maxfiles:
        query += " LIMIT %d" % maxfiles

    return get_query_results(cursor, query)

orderings = {}
orderings['faces'] = order_by_faces
orderings['cc'] = order_by_cc
orderings['id'] = order_by_id

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
<body><center><h1>Results generated with <a href="https://github.com/moshekaplan/Prioritize">Prioritize</a></h1><br/>"""

HTML_FOOTER = """</center></body></html> """

def write_file(fname, header_msg, imagesinfo):
    """This function will write the output to a file
    imagesinfo is a list of dictionaries, where each entry is the information
    for an image
    """

    #    filename, faces, screenshot, screenshot_fname, cc, cc_fname, jpeg.id, id_fname, contains_skin, skin_type, gps_data, text 
    with open(fname,'w') as fh:    
        fh.write(HTML_HEADER)
        fh.write(header_msg + '<br/>')
        for entry in imagesinfo:
            fh.write('<img src="%s"></><br/>\n' % entry['filename'])
            fh.write("<table>")
            fh.write("<tr><td>Filename:</td> <td>%s</td><br/>" % entry['filename'])
            if entry['gps_data']:
                fh.write("<tr><td>GPS Data:</td> <td>%s</td><br/>" % entry['gps_data'])
            if entry['model_data']:
                fh.write("<tr><td>Camera Model:</td> <td>%s</td><br/>" % entry['model_data'])
            if entry['date_data']:
                fh.write("<tr><td>Image Date:</td> <td>%s</td><br/>" % entry['date_data'])
            if entry['ocr_text']:
                fh.write("<tr><td>OCRed Text:</td> <td>%s</td><br/>" % entry['ocr_text'])
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

    parser.add_argument('--order-by', dest='order_by', action='store',
                      default='faces',
                      choices=orderings,
                      help="Choose which feature you'll use to prioritize the results (default is faces)")
                      
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

    order_by = orderings[args.order_by]
    results = order_by(cursor, maxfiles)
    header_msg = "The results are ordered by %s" % args.order_by

    write_file(output, header_msg, results)
    print "Open %s to see the results" % output

if __name__ == "__main__":
    main()
