'''
	photorg - An small photo organizer (v0.5).
        by Galileu Batista - galileu.batista at ifrn.edu.br
        contribution: Rodrigo Tavora
	Dez / 2017
'''

import os, sys, glob, shutil, re
import stat, mimetypes, piexif
import datetime, locale
import hashlib, binascii

ORG_BY_HOUR = "--h"
ORG_BY_DAY = "--d"
ORG_BY_MONTH = "--m"
ORG_BY_YEAR = "--y"
organizeOptions = [ ORG_BY_YEAR, ORG_BY_MONTH, ORG_BY_DAY, ORG_BY_HOUR]

SOURCE_DIR = "-d"
TARGET_DIR = "-o"

onlyPhotos = False
importEvents = False
eventFile = None
events = {}
eventSeparator = "--"
    
def locateAllFiles(dirs):
    global events
    log ("STATUS: Locating files in "+str(dirs)+" ...")
    allFiles = []
    for dir in dirs:
        for filename in glob.iglob(dir+'/**', recursive=True):
            if os.path.isfile(filename):
                allFiles.append({ 'name': filename,
                                  'size': os.stat(filename).st_size})
    return allFiles

def addType(allFiles):
    log ("STATUS: Detecting type of files ...")
    mime = mimetypes.MimeTypes()
    for file in allFiles:
        header = mime.guess_type(file['name'])
        if header[0] != None:
            header = header[0].split("/")
        if header[1] == 'jpeg':
           file['type'] = 'jpeg'
        elif header[0] == 'image':
           file['type'] = 'image'
        else:
            file['type'] = 'other'
    if onlyPhotos:
        log ("STATUS: Preserving only photos ...")
        allFiles = [file for file in allFiles if file['type'] != 'other']        
                
def addDate(allFiles):
    log ("STATUS: Searching for the best date for each file ...")
    now = datetime.datetime.now()
    for file in allFiles:
        fileName = file['name']
        dt = now
        
        try:
            header = piexif.load(fileName)
            exifdt = header["0th"][piexif.ImageIFD.DateTime].decode()
            dt = datetime.datetime.strptime(exifdt,  "%Y:%m:%d %H:%M:%S")
        except:
            try:
                # Try finding YYYYMMDD in filename, as saved by cameras and WhatsApp
                digInFileName= re.findall("\d+", os.path.basename(fileName))[0][:8]
                dt = datetime.datetime.strptime(digInFileName, "%Y%m%d")
            except:
                try:
                    dt = datetime.datetime.fromtimestamp (os.path.getmtime(fileName))
                except:
                    log ("WARN: Date wasn't found, using now() for "+fileName)
                    pass
        file['date'] = dt

def calcSHA256(fileName):
        fd = open(fileName,  "rb")
        m = hashlib.sha256()
        m.update(fd.read())
        fd.close()
        return binascii.hexlify(m.digest()).decode()
       
def checkForDuplicates(allFiles):
    log ("STATUS: Identifying duplicated files in source dirs ...")
    for file in allFiles:
        file ['dupFile'] = None
        
    for i in range(len(allFiles)):
        for j in range(i+1,  len(allFiles)):
            if (not allFiles[j]['dupFile'] and
                allFiles[i]['size'] == allFiles[j]['size']):
                if not allFiles[i].get('sha256', None):
                    allFiles[i]['sha256'] = calcSHA256(allFiles[i]['name'])
                if not allFiles[j].get('sha256', None):
                    allFiles[j]['sha256'] = calcSHA256(allFiles[j]['name'])

                if (allFiles[i]['sha256'] == allFiles[j]['sha256']):
                    allFiles[j]['dupFile'] = allFiles[i]['name']
                    log("WARN: Duplicated in source: "+allFiles[j]['name']+" --> "+\
                        allFiles[j]['dupFile'])


def checkForDupInTarget(allFilesSrc, allFilesTarget):
    log ("STATUS: Identifying source files duplicated in target dir ...")
    for fileSrc in allFilesSrc:
        for fileTarget in allFilesTarget:
            if (not fileSrc['dupFile'] and
                    fileSrc['size'] == fileTarget['size']):
                if not fileSrc.get('sha256', None):
                    fileSrc['sha256'] = calcSHA256(fileSrc['name'])
                if not fileTarget.get('sha256', None):
                    fileTarget['sha256'] = calcSHA256(fileTarget['name'])
                    
                if fileSrc['sha256'] == fileTarget['sha256']:
                    fileSrc['dupFile'] = fileTarget['name']
                    log("WARN: Duplicated in output: "+fileSrc['name']+" --> "+\
                        fileSrc['dupFile']+" not copied!")
                    break

def dirNameFromDate(date):
    if organizeBy == ORG_BY_YEAR:
        fullDirName = "/{0:4d}".format(date.year)
    if organizeBy == ORG_BY_MONTH:
        fullDirName = "/{0:4d}/{0:4d}-{1}".format(
                                date.year, date.strftime("%b"))
    if organizeBy == ORG_BY_DAY:
        fullDirName = "/{0:4d}/{0:4d}-{1}/{0:4d}-{1}-{2:02d}".format(
                                date.year, date.strftime("%b"),  date.day)
    if organizeBy == ORG_BY_HOUR:
        fullDirName = "/{0:4d}/{0:4d}-{1}/{0:4d}-{1}-{2:02d}-{3:02d}".format(
                                date.year, date.strftime("%b"),  date.day,
                                date.hour)

    fullDirNameEvents = ""
    for dirName in fullDirName.split('/'):
        fullDirNameEvents += dirName + events.get(dirName, '') + '/'
    
    return fullDirNameEvents
    
def getNameWithoutConfilct(targetDir, file):
    filename = os.path.basename(file['name'])
    targetFile = targetDir+"/"+filename
    while os.path.exists(targetFile):
        if not file.get('sha256', None):
            file['sha256'] = calcSHA256(file['name'])
        if (calcSHA256(targetFile) == file['sha256'] and 
            os.stat(targetFile).st_size == file['size']):
            return None
        ext = os.path.splitext(targetFile)[1]
        if ext =='':  ext = ".ext"
        targetFile += ext
        
    return targetFile
    
def copyFiles(outdir,  allFilesSrc, allFilesTarget):
    log ("STATUS: Copying files")
    copied = 0
    for file in allFilesSrc:
        if not file['dupFile']:
            targetDir = outdir + "/"+dirNameFromDate(file['date'])

            if not simMode and not os.path.exists(targetDir):
                os.makedirs(targetDir)
        
            targetFile =  getNameWithoutConfilct(targetDir, file) 
            if targetFile != None:
                if  os.path.basename(targetFile) == os.path.basename(file['name']):
                    log ("COPY: "+file['name']+ ' to '+targetFile)
                else:
                    log ("WARN: Conflict detected: COPY: "+file['name']+ ' to '+targetFile)
                if not simMode:
                    shutil.copy2(file['name'],  targetFile)
                copied += 1
            else:
                file['dupFile'] = targetFile
                log("WARN: Duplicated in destination dir: "+file['name']+" not copied!")                    
    if simMode:
        log ("STATUS: Number of files should be copied: "+str(copied))
    else:
        log ("STATUS: Number of files copied: "+str(copied))

def deleteDupFiles(allFiles):
    log ("STATUS: Deleting files")
    deleted = 0
    for file in allFilesSrc:
        if file['dupFile']:
            log ("DELETE: "+file['name']+" --> "+file['dupFile'])
            if not simMode:
                os.chmod(file['name'], stat.S_IWRITE)
                os.remove(file['name'])
            deleted += 1
    if simMode:
        log ("STATUS: Number of files should be deleted: "+str(deleted))
    else:
        log ("STATUS: Number of files deleted: "+str(deleted))
    
def log(msg):
    print (msg)

def importEventsFromDir(dir):
    log ("STATUS: Locating events in "+dir+" ...")
    for filename in glob.iglob(dir+'/**', recursive=True):
        if os.path.isdir(filename):
            dirName = os.path.basename(filename).split(eventSeparator)
            if len(dirName) == 2:
                events[dirName[0]] = eventSeparator+dirName[1]
    return events
                    
def addEventsFromFile(eventFile):
    log ("STATUS: Reading events from file "+eventFile+" ...")
    global events
    fdEvent = open(eventFile, "r")
    for event in fdEvent:
        event = event.strip()
        indSep = event.find(' ')
        if indSep > 0:
            events[event[:indSep]] = '--'+event[indSep+1:].strip()
        
    fdEvent.close()

def showHelpAndExit(msg=''):
    print ("photorg - An small photo organizer (v0.7).")
    print ("\t  by Galileu Batista - galileu.batista at ifrn.edu.br")
    print ("\t  contribution: Rodrigo Tavora")
        
    print ("usage: "+sys.argv[0]+" [--option | -option param] ")
    print ("\t"+ORG_BY_HOUR+" - organize files: a folder by hour")
    print ("\t"+ORG_BY_DAY+" - organize files: a folder by day (default)")
    print ("\t"+ORG_BY_MONTH+" - organize files: a folder by month")
    print ("\t"+ORG_BY_YEAR+" - organize files: a folder by year")
    print ("\t--h - Show this help")
    print ("\t--u - Show examples of usage")
    print ("\t--c - Check for duplicates in all subfolders in targetDir")
    print ("\t--p - Only consider photos (images) in processing")
    print ("\t--n - Simulation mode - files willn't be copied or deleted")
    print ("\t--r - Delete duplicated files in source dirs")
    print ("\t--R - Only delete duplicated files in source dirs. No copy at all")
    print ("\t--i - Identify events in target-dir")
    print ("\t      if output folder has an event name, it will be used")
    print ("\t-e event-file - a file with descriptions for events on dates")
    print ("\t                event names will be appended to folder name")
    print ("\t\tformat and example (do not use -- in event names):")
    print ("\t\t\t2017         current-year")
    print ("\t\t\t2017-mar     test-on-march")
    print ("\t\t\t2017-oct-21  niver-gio")
    print ("\t-l locale     - Locale for choose month names (default: pt)")
    print ("\t-d source-dir - Where files will be copied from (default: .)")
    print ("\t                Can be used multiple times.")
    print ("\t-o target-dir - Where files will be copied to (default: ./classified)")
    
    print (msg)
    
    sys.exit(1)

def showExamplesAndExit():
    print ("Usage examples....")
    print ("\n{} --d -d c:/unclass -o c:/class".format(sys.argv[0]))
    print ("\tCopy files from c:/unclass in c:/class - day basis.")
    print ("\n{} --y --n -d c:/unclass -o c:/class".format(sys.argv[0]))
    print ("\tsimululate organization from c:/unclass to c:/class - year basis")
    print ("\tbecause --n, **no copies and/or deletions are done** at all.")
    print ("\n{} --m -l en -d c:/unclass -o c:/class".format(sys.argv[0]))
    print ("\tCopy files from c:/unclass to c:/class - month basis")
    print ("\tuse month names in english (locate: -l en).")
    print ("\n{} --r --m -d c:/unclass -o c:/class".format(sys.argv[0]))
    print ("\tCopy files to c:/class and **remove duplicates** in c:/unclass")
    print ("\tduplicates are checked (size,sha256) in source dirs.")
    print ("\n{} --c --r --m -d c:/unclass -o c:/class".format(sys.argv[0]))
    print ("\tCopy files to c:/class and **remove duplicates** in c:/unclass")
    print ("\tduplicates are checked (size,sha256) against sources and target dirs.")
    print ("\n{} --c --R --m -d c:/unclass -o c:/class".format(sys.argv[0]))
    print ("\t**No copy** any files (--R), but **remove duplicates** in source dirs")
    print ("\tduplicates are checked (size,sha256) against source and target dirs.")
    print ("\n{} --c --r --p --m -d c:/unclass -o c:/class".format(sys.argv[0]))
    print ("\tCopy **only pictures** to c:/class and **remove duplicates** in source")
    print ("\tduplicates are checked (size,sha256) against source and target dirs.")
    
    sys.exit(0)
    
def processOptions():
    global  organizeBy, importEvents, eventFile, sourceDir
    global  targetDir, fullChkDup, simMode, delDup, onlyDelDup, onlyPhotos
    
    if len(sys.argv) < 2: 
        showHelpAndExit()

    sourceDir = []
    targetDir = None
    organizeBy = ORG_BY_DAY
    fullChkDup = False
    simMode = False
    delDup = False
    onlyDelDup = False
    locale.setlocale(locale.LC_ALL, "pt")
    
    try:        
        nextArg = 1
        while nextArg < len(sys.argv):
            if sys.argv[nextArg] in organizeOptions:
                organizeBy = sys.argv[nextArg]
            elif sys.argv[nextArg] == '--c':
                fullChkDup = True
            elif sys.argv[nextArg] == '--r':
                delDup = True
            elif sys.argv[nextArg] == '--R':
                onlyDelDup = True
            elif sys.argv[nextArg] == '--n':
                simMode = True
            elif sys.argv[nextArg] == '--i':
                importEvents = True
            elif sys.argv[nextArg] == '--p':
                onlyPhotos = True
            elif sys.argv[nextArg] == '-e' and (nextArg+1) < len(sys.argv):
                eventFile = sys.argv[nextArg+1]
                nextArg += 1
            elif sys.argv[nextArg] == '-d' and (nextArg+1) < len(sys.argv):
                sourceDir.append(sys.argv[nextArg+1])
                nextArg += 1
            elif sys.argv[nextArg] == '-o' and (nextArg+1) < len(sys.argv):
                targetDir = sys.argv[nextArg+1]
                nextArg += 1
            elif sys.argv[nextArg] == '-l' and (nextArg+1) < len(sys.argv):
                locale.setlocale(locale.LC_ALL, sys.argv[nextArg+1])
                nextArg += 1
            elif sys.argv[nextArg] == '--u':
                showExamplesAndExit()
            elif sys.argv[nextArg] == '--h':
                showHelpAndExit()
            else:
                showHelpAndExit("ERROR: Invalid option: "+sys.argv[nextArg])
            nextArg += 1

        if len(sourceDir) == 0:
            sourceDir = ["."]
            
        if targetDir == None:
            targetDir = "./classified"
            
        log ("Option: '{}' SourceDir: '{}' TargetDir: '{}' Locale: {}".format(
             organizeBy, sourceDir, targetDir, locale.getlocale()))
    except Exception as e:
        showHelpAndExit(str(e)+" current arg: "+sys.argv[nextArg])

def printFiles(allFiles):
    print ("*****************************")
    for file in allFiles:
        print(file)
    print ("*****************************")


if __name__ == "__main__":
    processOptions()
    if importEvents:
        events = importEventsFromDir(targetDir)
    if eventFile:
        addEventsFromFile(eventFile)

    allFilesSrc = locateAllFiles(sourceDir)        
    addType(allFilesSrc)
    addDate(allFilesSrc)
    checkForDuplicates(allFilesSrc)

    if fullChkDup:
        allFilesTarget = locateAllFiles([targetDir])        
        checkForDupInTarget(allFilesSrc, allFilesTarget)
    else:
        allFilesTarget = []

    if onlyDelDup:
        deleteDupFiles(allFilesSrc)
    else:
        copyFiles(targetDir,  allFilesSrc, allFilesTarget)
        if delDup:
            deleteDupFiles(allFilesSrc)
        
    log ("STATUS: Processing finished!!!!")

