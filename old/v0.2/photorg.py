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

def locateAllFiles(dir):
    log ("Locating files in "+dir+" ...")
    allFiles = []
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
    if sys.argv[1] == ORG_BY_YEAR:
        dirname = "{0:4d}/".format(date.year)

    if sys.argv[1] == ORG_BY_MONTH:
        dirname = "{0:4d}/{0:4d}-{1}/".format(
                                date.year, date.strftime("%b"))
    if sys.argv[1] == ORG_BY_DAY:
        dirname = "{0:4d}/{0:4d}-{1}/{0:4d}-{1}-{2:02d}/".format(
                                date.year, date.strftime("%b"),  date.day)
    if sys.argv[1] == ORG_BY_HOUR:
        dirname = "{0:4d}/{0:4d}-{1}/{0:4d}-{1}-{2:02d}-{3:02d}/".format(
                                date.year, date.strftime("%b"),  date.day,  date.hour)
                    
    if not os.path.exists(outdir+"/"+dirname):
        os.makedirs(outdir+"/"+dirname)
        
    return dirname
    
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
    
def printFiles(allFiles):
    print ("*****************************")
    for file in allFiles:
        print(file)
    print ("*****************************")

if __name__ == "__main__":
    if len (sys.argv) != 4:
        print ("photorg - A small photo organizer (v0.2).")
        print ("\t  by Galileu Batista - galileu.batista at ifrn.edu.br")
        print ("\t  contribution: Rodrigo Tavora")
        
        print ("usage: "+sys.argv[0]+" "+ORG_BY_HOUR+"|"+ORG_BY_DAY+"|"+\
                                ORG_BY_MONTH+"|"+ORG_BY_YEAR+" source-dir target-dir")
        print ("\t\t"+ORG_BY_HOUR+" organize files - a folder by hour")
        print ("\t\t"+ORG_BY_DAY+" organize files - a folder by day")
        print ("\t\t"+ORG_BY_MONTH+" organize files - a folder by month")
        print ("\t\t"+ORG_BY_YEAR+" organize files - a folder by year")
        sys.exit(1)

    allFiles = locateAllFiles(sys.argv[2])
    addType(allFiles)
    addDate(allFiles)
    addHashes(allFiles)
    removeDuplicate(allFiles)
    copyFiles(sys.argv[3],  allFiles)
    log ("Processing finished!!!!")

