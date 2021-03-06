import os
import sys
import glob
import imghdr
import piexif
import datetime
import hashlib
import binascii
import shutil

ORG_BY_HOUR = "-h"
ORG_BY_DAY = "-d"
ORG_BY_MONTH = "-m"
ORG_BY_YEAR = "-y"
organizeOptions = [ ORG_BY_YEAR, ORG_BY_MONTH, ORG_BY_DAY, ORG_BY_HOUR]

importEvents = False
eventFile = None
events = {}
eventSeparator = "--"
    
def locateAllFiles(dir):
    global events
    log ("Locating files in "+dir+" ...")
    allFiles = []
    print ("log "+dir)
    for filename in glob.iglob(dir+'/**', recursive=True):
        if os.path.isfile(filename):
            allFiles.append({ 'name': filename,
                              'size': os.stat(filename).st_size})
    return allFiles

def addType(allFiles):
    log ("Detecting type of files ...")
    for file in allFiles:
        header = imghdr.what(file['name'])
        if header == 'jpeg':
           file['type'] = 'jpg'
        elif header != None:
           file['type'] = 'img'
        else:
            file['type'] = 'all'

def addDate(allFiles):
    log ("Searching for the best date for each file ...")
    for file in allFiles:
        filename = file['name']
        dt = None
        if file['type'] == 'jpg':
            header = piexif.load(filename)
            try:
                exifdt = header["0th"][piexif.ImageIFD.DateTime].decode()
                dt = datetime.datetime.strptime(exifdt,  "%Y:%m:%d %H:%M:%S")
            except:
                pass
        
        if dt == None: 
            try: # Arquivos do WhatsApp
                wapos = filename.rfind("-WA")
                whatsDate = filename[wapos-8:wapos]
                dt = datetime.datetime.strptime(whatsDate,  "%Y%m%d")
            except:
                dt =datetime.datetime.fromtimestamp (os.path.getmtime(filename))
        file['date'] = dt

def calcSHA256(filename):
        fd = open(filename,  "rb")
        m = hashlib.sha256()
        m.update(fd.read())
        fd.close()
        return binascii.hexlify(m.digest()).decode()

def addHashes(allFiles):
    log ("Calculating hashes ...")
    for file in allFiles:
        file['sha256'] = calcSHA256(file['name'])
        

def removeDuplicate(allFiles):
    log ("Identifying duplicated files ...")
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
                                date.year, date.strftime("%b"),  date.day,  date.hour)

    fullDirNameEvents = "/"
    for dirName in fullDirName.split('/'):
        fullDirNameEvents += dirName + events.get(dirName, '') + '/'

    
    if not os.path.exists(outdir+"/"+fullDirNameEvents):
        os.makedirs(outdir+"/"+fullDirNameEvents)
        
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
    
def copyFiles(outdir,  allFiles):
    copied = 0
    for file in allFiles:
        if not file['dup']:
            targetDir = outdir + "/"+dirNameFromDate(outdir,  file['date'])
            targetFile =  getNameWithoutConfilct(targetDir, file) 
            if targetFile != None:
                if  os.path.basename(targetFile) == os.path.basename(file['name']):
                    log ("Copying "+file['name']+ ' to '+targetFile)
                else:
                    log ("Conflict detected: copying "+file['name']+ ' to '+targetFile)
                shutil.copy2(file['name'],  targetFile)
                copied += 1
            else:        
                log("Duplicated in destination: "+file['name']+" not copied!")                    
        else:
            log("Duplicated in origin: "+file['name']+" not copied!")
    log ("Files copied: "+str(copied))
    
def log(msg):
    print (msg)

def showHelpAndExit():
    print ("photorg - A small photo organizer (v0.3).")
    print ("\t  by Galileu Batista - galileu.batista at ifrn.edu.br")
    print ("\t  contribution: Rodrigo Tavora")
        
    print ("usage: "+sys.argv[0]+" "+ORG_BY_HOUR+"|"+ORG_BY_DAY+"|"+\
                                ORG_BY_MONTH+"|"+ORG_BY_YEAR+\
                                " [-e event-file | -i] source-dir target-dir")
    print ("\t\t"+ORG_BY_HOUR+" organize files - a folder by hour")
    print ("\t\t"+ORG_BY_DAY+" organize files - a folder by day")
    print ("\t\t"+ORG_BY_MONTH+" organize files - a folder by month")
    print ("\t\t"+ORG_BY_YEAR+" organize files - a folder by year")
    print ("\t\t-e event-file - a file with descriptions for events on dates")
    print ("\t\t                event names will be appended to folder name")
    print ("\t\t\tformat and example (do not use -- in event names):")
    print ("\t\t\t\t2017         current-year")
    print ("\t\t\t\t2017-Mar     test-on-march")
    print ("\t\t\t\t2017-Oct-21  niver-gio")
    print ("\t\t-i identify events in target-dir")
    print ("\t\t   if output folder has an event name, it will be used")
    
    sys.exit(1)

def importEventsFromDir(dir):
    log ("Locating events in "+dir+" ...")
    for filename in glob.iglob(dir+'/**', recursive=True):
        if os.path.isdir(filename):
            dirName = os.path.basename(filename).split(eventSeparator)
            if len(dirName) == 2:
                events[dirName[0]] = eventSeparator+dirName[1]
    return events
                    
def addEventsFromFile(eventFile):
    log ("Reading events from file "+eventFile+" ...")
    global events
    fdEvent = open(eventFile, "r")
    for event in fdEvent:
        event = event.strip()
        indSep = event.find(' ')
        if indSep > 0:
            events[event[:indSep]] = '--'+event[indSep+1:].strip()
        
    fdEvent.close()

def processOptions():
    global organizeBy, importEvents, eventFile, sourceDir, targetDir
    
    if len(sys.argv) >= 4 and sys.argv[1] in organizeOptions:
        organizeBy = sys.argv[1]
    else:
        showHelpAndExit()

    nextArg = 2
    if sys.argv[nextArg] == '-e':
        eventFile = sys.argv[nextArg+1]
        nextArg += 2

    if nextArg < len(sys.argv) and sys.argv[nextArg] == '-i':
        importEvents = True
        nextArg += 1

    if nextArg < len(sys.argv):
        sourceDir = sys.argv[nextArg]
        nextArg += 1
    else:
        showHelpAndExit()
        
    if nextArg < len(sys.argv):
        targetDir = sys.argv[nextArg]
        nextArg += 1
    else:
        showHelpAndExit()

    log ("Option: '{}' SourceDir: '{}' TargetDir: '{}'".format(
         organizeBy, sourceDir, targetDir))
    
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

    allFiles = locateAllFiles(sourceDir)        
    addType(allFiles)
    addHashes(allFiles)
    addDate(allFiles)
    removeDuplicate(allFiles)
    copyFiles(targetDir,  allFiles)
    log ("Processing finished!!!!")

