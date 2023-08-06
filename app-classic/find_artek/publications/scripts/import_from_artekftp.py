# -*- coding: utf_8 -*-

from __future__ import unicode_literals
# my_string = b"This is a bytestring"
# my_unicode = "This is an Unicode string"

import chardet
import ftputil
import os.path
import re
import pdb
import time
import pickle

from publications import models

ftp_encoding = 'ISO-8859-2'
re_repnum = re.compile(r"\d{2}-\d{2}")
re_2006 = re.compile(r"2006/(?=\d{2}\s)")

try:
    tmp = pdf_paths
    del tmp
except:
    pdf_paths = dict()

def ftp_connect_to_host():
    host = None
    i = 0
    while i<=5:
        i += 1
        try:
            host = ftputil.FTPHost('artekftp.byg.dtu.dk', 'anonymous', 'find.artek')
#            host.chdir('Rapporter')
#            basedir = host.getcwd()

#                host.chdir(basedir)
#            host.chdir(p.year.encode())
        except:
            print "attempt {0} failed...!".format(i)
            success = False
            try:
                host.close()
            except:
                pass
            continue

        success = True
        break

    return host

def get_dirlist(host):
    names = []
    i = 0
    while i<=5:
        i += 1
        try:
            names = host.listdir(host.curdir)
        except:
            success = False
            continue
        success = True
        break

    alltext = []
    alltext.extend(names)
    alltext = alltext[0].join(alltext[1:])
    encoding = chardet.detect(alltext)['encoding']

    for i in range(len(names)):
        names[i]=names[i].decode(encoding)

    return names

def ftp_chdir(host, path):
    i = 0
    while i<=5:
        i += 1
        try:
            if host.path.isdir(path):
                host.chdir(path)
        except:
            success = False
            continue
        success = True
        break

    return success


def get_pdf_paths(host, startpath=None):
    """ Returns a dictionary containing path to pdf files in the
        directory tree below startpath (or current path if None).
        key is the filename without extension '.pdf'
        value is a list of paths including filename and extension
        to files with the filename in key.

    """

    if not startpath:
        startpath = host.getcwd()

    file_dict = dict()
    file_dict['::extra::'] = dict()

    i = 0
    for (path, dirs, files) in host.walk(startpath):
        alltext = [path]
        alltext.extend(dirs)
        alltext.extend(files)
        alltext = path.join(alltext)
        encoding = chardet.detect(alltext)['encoding']
        path = path.decode(encoding)
        try:
            print path
        except:
            pass
        pdf_files = []
        report_found = False
        for f in files:
            f = f.decode(encoding)
            fname,fext = os.path.splitext(f)

            repnums_in_fname = re.findall(re_repnum, fname)
            if repnums_in_fname and repnums_in_fname[0] == fname:
                report_found = True
                try:
                    print "-> ({0}) Report found!".format(fname)
                except:
                    pass

            if fext == '.pdf':
                #fname = fname.decode(encoding)
                pdf_files.append(f)
                if fname in file_dict:
                    file_dict[fname].append(host.path.join(path, f))
                else:
                    file_dict[fname] = [host.path.join(path, f)]

        # Fix for 2006, where dirs are named 2006/01, 2006/02, not 2006/06-01 etc.
        tmp = re.sub(re_2006,r'\g<0>06-',path)
        rep_num = re.findall(re_repnum, tmp)
        if not report_found and rep_num:
            #print rep_num
            #pdb.set_trace()
            if "Rapport.pdf" in pdf_files:
                report_path = host.path.join(path, "Rapport.pdf")
                try:
                    print "-> ({0}) {1} added to ::extra:: dict".format(rep_num[0], "Rapport.pdf")
                except:
                    pass
            elif len(pdf_files) == 1:
                report_path = host.path.join(path, pdf_files[0])
                try:
                    print "-> ({0}) {1} added to ::extra:: dict".format(rep_num[0], "Rapport.pdf")
                except:
                    pass
            else:
                continue # skip last part if report file cannot be guessed

            if rep_num[0] in file_dict['::extra::']:
                file_dict['::extra::'][rep_num[0]].append(report_path)
            else:
                file_dict['::extra::'][rep_num[0]] = [report_path]

    return file_dict


def get_pdf(pubs, user, pdf_path_dict=None, reload=False):
    # Function to retrieve pdf-files for report from
    # ARTEK ftp server

    # Loop thorugh all publications passed
    # Guess the probable path. artekftp.byg.dtu.dk/reports/[year]
    # name should be report number: xx-xx.pdf
    # if not found, try path artekftp.byg.dtu.dk/reports/[year]/[xx-xx]
    # if path exist, but file does not, try walking subdirs
    # if not found look for pdf-filename.lower() containing ['rapport','report']
    # when file is found, download it, and upload_to /reports/[year]/

    # presently do not handle other files

    global pdf_paths

    if isinstance(pubs, models.Publication):
        pubs = [pubs]


    if pdf_path_dict:
        pdf_paths = pdf_path_dict

    if not pdf_paths and not reload:
        try:
            pkl_file = open('ftp_pdf_paths.pkl', 'rb')
            pdf_paths = pickle.load(pkl_file)
            pkl_file.close()
        except:
            pass


    if not pdf_paths:
        host = ftp_connect_to_host()

        if not host:
            print "aborting..."
            return

        print "Getting pdf paths from server..."
        pdf_paths = get_pdf_paths(host, startpath='Rapporter')
        host.close()

        output = open('ftp_pdf_paths.pkl', 'wb')
        # Pickle dictionary using protocol 0.
        pickle.dump(pdf_paths, output)
        output.close()

    for k,v in sorted(pdf_paths.items()):
        if k and len(k)>5 and k[2] == '-':
            try:
                print "{0}:\t{1}".format(k,v)
            except:
                pass

    if not pdf_paths:
        print "Could not get/parse directory structure. Aborting..."
        return

    for p in pubs:
        # skip publications that have a file attached already
        if p.file:
            continue
        # skip publications that don't have a number
        if not p.number:
            continue

        print " "
        print "Report {0}".format(p.number)

        fname = p.number.strip()
        if fname in pdf_paths:
            if len(pdf_paths[fname]) > 1:
                print "More than one file found, aborting..."
                continue
            pdffile = pdf_paths[fname][0]
        elif fname in pdf_paths['::extra::']:
            if len(pdf_paths['::extra::'][fname]) > 1:
                print "More than one file found, aborting..."
                continue
            pdffile = pdf_paths['::extra::'][fname][0]
        else:
            print "Pdf file not found, aborting..."
            continue

        print "Opening connection to server..."
        host = ftp_connect_to_host()

        if not host:
            print "Aborting this report..."
            continue

        if host.path.isfile(pdffile.encode(ftp_encoding)):
            print "Closing ftp-connection"
            host.close()
            # the file exists
            # now download file...
            fileurl = urljoin('ftp://artekftp.byg.dtu.dk/', pdffile)

            try:
                furl = fileurl
                print "ready to retrieve file"
                register_pdffile(furl, p, user)
                print "finished retrieving file"
            except Exception as e:
                print "error: {0}".format(e)

        else:
            print "pdf-file not found..."
            print "Closing ftp-connection"
            host.close()

    return pdf_paths

        #names = get_dirlist(host)
        #if not names:
        #    print "Could not get directory listing. Aborting this report..."
        #    host.close()
        #    continue


        #pdfname = b"{0}.pdf".format(p.number)

        #if pdfname not in names:
        #    if p.number.encode() in names and host.path.isdir(p.number.encode()):
        #        trydir = p.number.encode()
        #    else:
        #
        #        number = p.number.strip()
        #        if len(number)>4:
        #            number = number[0:5]
        #
        #        for n in names:
        #            if not host.path.isdir(n):
        #                continue
        #
        #            if n.strip().find(number.encode()) > -1:
        #                trydir = n
        #            elif n.strip().startswith(number[3:]):
        #                trydir = n
        #
        #    success = False
        #    success = ftp_chdir(host, trydir)
        #    if success:
        #        names = get_dirlist(host)

        #if pdfname in names and host.path.isfile(pdfname):
        #    # the file exists
        #    filepath = host.path.join(host.getcwd(),pdfname)
        #    # now download file...
        #    fileurl = urljoin('ftp://artekftp.byg.dtu.dk/', filepath)
        #    try:
        #        register_pdffile(fileurl, p, user)
        #    except Exception as e:
        #        print "error: {0}".format(e)
        #
        #else:
        #    print "Could not get dirlist, or pdf-file not found..."
        #
        #print "Closing connection"
        #host.close()



#        if pdfname in names and host.path.isfile(pdfname):
#            # the file exists
#            filepath = host.path.join(host.getcwd(),pdfname)
#        elif p.number.encode() in names:
#            success = ftp_chdir(host, p.number.encode())
#            if success:
#
#            names = get_dirlist(host)
#            if not names:
#                print "Could not get directory listing. Aborting this report..."
#                host.close()
#                continue
#
#            if pdfname in names:
#                # the file exists
#                filepath = host.path.join(host.getcwd(),pdfname)
#            else:
#                # not found, skip
#                print "pdf-file not found on server"
#                print "Closing connection"
#                host.close()
#                continue
#        else:
#            # not found, skip
#            print "pdf-file not found on server"
#            print "Closing connection"
#            host.close()
#            continue
#
#        # now download file...
#        fileurl = urljoin('ftp://artekftp.byg.dtu.dk/', filepath)
#        try:
#            register_pdffile(fileurl, p, user)
#        except Exception as e:
#            print "error: {0}".format(e)
#
#        print "Closing connection"
#        host.close()


def register_pdffile(url, pub, user, fname=None):
    # Get a file from the specified url and
    # save it to the model.

    if not pub.type.type == 'STUDENTREPORT':
        raise ValueError("PDF-download only implemented for STUDENTREPORT")

    if not (pub.number or fname):
        raise ValueError("A filename or publication number must be specified!")
    elif pub.number and not fname:
        fname = pub.number

    print "Retrieving pdf-file from: {0}".format(url)

    # New filename = xx-xx.yyy
    _u , fext = os.path.splitext(os.path.basename(url))
    fname = fname+fext

    #tmppath = os.path.join('tmp',fname)
    #filepath = default_storage.save(fpath, ContentFile(request.FILES['file'].read()))

    print "calling get_file_from_url"
    pdffile = get_file_from_url(url)
    print "back from get_file_from_url"

    if not pdffile:
        return # if no file obtained

    # Upload files to /reports/[year]/xxxx.pdf
    upload_dir = ['reports','{0}'.format(pub.year)]

    myfile = models.FileObject()

    # Set mandatory fields
    myfile.modified_by = user
    myfile.created_by = user
    myfile.original_URL = url
    myfile.description = "Report file downloaded from artekftp.byg.dtu.dk"

    # Bypass normal 'upload_to' path generation by setting it directly
    myfile.upload_to = os.path.join(*upload_dir).replace(' ','_')
    # All spaces are replaced by underscores...

    # Save to database to generate primary_key before adding file
    myfile.save()

    # Save the temp file to an actual file at the correct location
    myfile.file.save(fname, pdffile, save=True)

    print "File saved to: {0}".format(myfile.file.name)
    # Make sure temp-file is deleted
    pdffile.close()
    myfile.original_URL = url

    # Add the file to the m2m field on the publication
    pub.file = myfile
    pub.save()


def urljoin(*pieces):
    # function to join a list of strings into an url
    # redundant '/' are stripped, but no validation occurs
    return '/'.join([s.strip('/') for s in pieces])


def get_file_from_url(url):
    # Loads the file located at URL and saves it to a temporaryfile.
    # The temporary file is wrapped by the django File() class
    # and returned for further use.
    #
    # e.g.:
    #
    # im.file.save(file_name, get_file_from_url('http://www.some.url'))

    from django.core.files import File
    from django.core.files.temp import NamedTemporaryFile
    import urllib2

    success = False
    fails = 0
    while fails < 3:
        file_temp = NamedTemporaryFile()
        try:
            print "  Attempt {0}".format(fails+1)
            file_temp.write(urllib2.urlopen(url.encode(ftp_encoding),None,timeout=15).read())
            success = True
            break
        except Exception as detail:
            print "HTTP error: ", detail
            file_temp.close()
            fails += 1
        time.sleep(2)

    if not success:
        return None

    file_temp.flush()

    return File(file_temp)
