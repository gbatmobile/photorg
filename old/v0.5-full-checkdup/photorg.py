import os, sys, glob, shutil
import imghdr, piexif
import datetime, locale
import hashlib, binascii

ORG_BY_HOUR = "--h"
ORG_BY_DAY = "--d"
ORG_BY_MONTH = "--m"
ORG_BY_YEAR = "--y"
organizeOptions = [ ORG_BY_YEAR, ORG_BY_MONTH, ORG_BY_DAY, ORG_BY_HOUR]

SOURCE_DIR = "-d"
TARGET_DIR = "-o"

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
    for file in allFiles:
        header = imghdr.what(file['name'])
        if header == 'jpeg':
           file['type'] = 'jpg'
        elif header != None:
           file['type'] = 'img'
        else:
            file['type'] = 'all'

def addDate(allFiles):
    log ("STATUS: Searching for the best date for each file ...")
    now = datetime.datetime.now()
    for file in allFiles:
        filename = file['name']
        dt = now
        
        try:
            header = piexif.load(filename)
            exifdt = header["0th"][piexif.ImageIFD.DateTime].decode()
            dt = datetime.datetime.strptime(exifdt,  "%Y:%m:%d %H:%M:%S")
        except:
            try:
                wapos = filename.rfind("-WA")
                whatsDate = filename[wapos-8:wapos]
                dt = datetime.datetime.strptime(whatsDate,  "%Y%m%d")
            except:
                try:
                    dt = datetime.datetime.fromtimestamp (os.path.getmtime(filename))
                except:
                    log ("WARN: Date wasn't found, using now() for "+filename)
                    pass
        file['date'] = dt

def calcSHA256(filename):
        fd = open(filename,  "rb")
        m = hashlib.sha256()
        m.update(fd.read())
        fd.close()
        return binascii.hexlify(m.digest()).decode()

def addHashes(allFiles):
    log ("STATUS: Calculating hashes ...")
    for file in allFiles:
        log ("HASHING: "+ file['name'])
        file['sha256'] = calcSHA256(file['name'])
        
def getFileIn(fileToCheck, allFiles):
    for file in allFiles:
        if (file['size'] == fileToCheck['size'] and
            file['sha256'] == fileToCheck['sha256'] and
            file['name'].upper() != fileToCheck['name'].upper()):
            return file
    return None

def removeDuplicate(allFiles):
    log ("STATUS: Identifying duplicated files in source dirs ...")
    for file in allFiles:
        file ['dup'] = False
        
    for i in range(len(allFiles)):
        for j in range(i+1,  len(allFiles)):
            if (allFiles[i]['sha256'] == allFiles[j]['sha256'] and
                allFiles[i]['size'] == allFiles[j]['size']):
               allFiles[j]['dup'] = True

def dirNameFromDate(outdir,  date):
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

    fullDirNameEvents = "/"
    for dirName in fullDirName.split('/'):
        fullDirNameEvents += dirName + events.get(dirName, '') + '/'
    
    return fullDirNameEvents
    
def getNameWithoutConfilct(targetDir, file):
    filename = os.path.basename(file['name'])
    targetFile = targetDir+"/"+filename
    while os.path.exists(targetFile):
        if (calcSHA256(targetFile)  == file['sha256'] and 
            os.stat(targetFile).st_size == file['size']):
            return None
        ext = os.path.splitext(targetFile)[1]
        if ext =='':  ext = ".ext"
        targetFile += ext
        
    return targetFile
    
def copyFiles(outdir,  allFilesSrc, allFilesTarget):
    copied = 0
    for file in allFilesSrc:
        if fullChkDup:
            fileInTarget = getFileIn (file, allFilesTarget)
        else:
            fileInTarget = None
            
        if not file['dup'] and not fileInTarget:
            targetDir = outdir + "/"+dirNameFromDate(outdir,  file['date'])

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
                log("WARN: Duplicated in destination dir: "+file['name']+" not copied!")                    
        else:
            if file['dup']:
                log("WARN: Duplicated in origin: "+file['name']+" not copied!")
            else:
                log("WARN: Duplicated in output tree: "+file['name']+" --> "+\
                    fileInTarget['name']+" not copied!")
    if simMode:
        log ("STATUS: Number of files should be copied: "+str(copied))
    else:
        log ("STATUS: Number of files copied: "+str(copied))
    
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
    print ("photorg - An small photo organizer (v0.5).")
    print ("\t  by Galileu Batista - galileu.batista at ifrn.edu.br")
    print ("\t  contribution: Rodrigo Tavora")
        
    print ("usage: "+sys.argv[0]+" [--option | -option param] ")
    print ("\t"+ORG_BY_HOUR+" - organize files: a folder by hour")
    print ("\t"+ORG_BY_DAY+" - organize files: a folder by day (default)")
    print ("\t"+ORG_BY_MONTH+" - organize files: a folder by month")
    print ("\t"+ORG_BY_YEAR+" - organize files: a folder by year")
    print ("\t--c - Check for duplicates in all subfolders in targetDir")
    print ("\t--n - Simulation mode - files willn't be copied")
    print ("\t--i - identify events in target-dir")
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


def processOptions():
    global  organizeBy, importEvents, eventFile, sourceDir
    global  targetDir, fullChkDup, simMode
    
    if len(sys.argv) < 2: 
        showHelpAndExit()

    sourceDir = []
    targetDir = None
    organizeBy = ORG_BY_DAY
    fullChkDup = False
    simMode = False
    locale.setlocale(locale.LC_ALL, "pt")
    
    try:        
        nextArg = 1
        while nextArg < len(sys.argv):
            if sys.argv[nextArg] in organizeOptions:
                organizeBy = sys.argv[nextArg]
            elif sys.argv[nextArg] == '--c':
                fullChkDup = True
            elif sys.argv[nextArg] == '--n':
                simMode = True
            elif sys.argv[nextArg] == '--i':
                importEvents = True
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
    addHashes(allFilesSrc)
    removeDuplicate(allFilesSrc)

    if fullChkDup:
        allFilesTarget = locateAllFiles([targetDir])        
        addHashes(allFilesTarget)
    else:
        allFilesTarget = []

    copyFiles(targetDir,  allFilesSrc, allFilesTarget)
    log ("STATUS: Processing finished!!!!")

