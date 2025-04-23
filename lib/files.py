import os
import shutil
import json
import logging
import hashlib
import stat
import subprocess

from paramiko import sftp_attr

from dotenv import load_dotenv
from datetime import datetime
from getpass import getpass

from lib.dataformats import *


print("Is dotenv:" + str(load_dotenv()))

#logging.basicConfig(level=logging.DEBUG)

class ENVPaths():
    def __init__(self):
        self.virutalEnvLoc = os.environ['VIRTUAL_ENV'] 
        self.appFolder = self.virutalEnvLoc.strip("venv")
        self.configFolder = self.appFolder + os.environ['CONFIG_FOLDER']
        self.keysFolder = self.appFolder + os.environ['KEYS_FOLDER']
        self.globalConfig = self.configFolder + "global.json"
        self.libFolder = self.appFolder + os.environ['LIB_FOLDER']

class OSCmd(ENVPaths):
    def __init__(self):
        super().__init__() 
        self.platform = None
        self.platformCommands = None
        self.osdictPath = self.libFolder + "osdict.json"
        self.osdict = None
        self._GetOsDict()

    def _GetOsDict(self):
        with open(self.osdictPath) as f:
            self.osdict = json.load(f)
        self.platformCommands = self.osdict["platformCMD"]

    def CheckRemoveSafePaths(self, path):
        if not path in self.osdict[self.platform]["unsafePaths"]:
            return True
        return False

    def GetSystemSlash(self, platform):
        slash = self.osdict[platform]["slash"]
        return slash

    # Maybe split in a future where cmd redirects to certain cmd...
    # For now we have only Hash
    def GetMd5HashCMD(self, platform) -> str:
        """
        Returns Hash command as string to use with method str.format()
        :param platform: platform set by the class
        """
        cmdDict = self.osdict[platform]['md5']
        cmd =  str(cmdDict["base"] + " {} " + cmdDict["flags"] + " " + cmdDict["pipeline"])
        return cmd


class __CommonManagement():
    def __init__(self):
        pass

    def _IsDir(self, st_mode: str):
        return stat.S_ISDIR(st_mode)

    def _CombineMirrorAndTarget(
        self, foundPath, fillPath, remoteMirror, originaRemotelFolder, isDir
    ):
        """
        Returns proper SyncTask configure to account "remoteMirror" value.
        """
        if remoteMirror:
            return SyncTask(
                remoteMirror=remoteMirror,
                mirrorPath=foundPath,
                targetPath=fillPath + foundPath.removeprefix(originaRemotelFolder),
                isDir=isDir,
            )
        else:
            return SyncTask(
                remoteMirror=remoteMirror,
                mirrorPath=fillPath + foundPath.removeprefix(originaRemotelFolder),
                targetPath=foundPath,
                isDir=isDir,
            )

class RemoteFilesAndDirs(OSCmd, __CommonManagement):
    def __init__(self, client, sftp):
        super().__init__() 
        self.client = client
        self.sftp = sftp
        self.__SetPlatform()

    def __SetPlatform(self):
        logging.info("Attempting Finding Remote Platform")
        for t, cmd in self.platformCommands.items():
            err = None
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd)
                err = self.__decodeSSHCommandOutput(stderr)
            except Exception as e:
                logging.error(e)
                raise(e)
            if err:
                logging.info("Not {} platform".format(t))
            else:
                logging.info("Found remote platform: {}".format(t))
                self.platform = t
                break

        if not self.platform:
            msg = "Could not find platform for the config. Couldn't execute command"
            logging.error(msg)
            raise(Exception(msg))

    def _ValidationMirrorTargetPath(self, syncObj):
        filename = syncObj.GetRemotePath().split("/")[-1]
        if not syncObj.GetLocalPath().split("/")[-1] == filename:
            msg = "Config wrongly created - File matched with Folder in 'paths': {}".format(syncObj.__dict__)
            logging.error(msg)
            raise (TypeError(msg))

    def __decodeSSHCommandOutput(self,output):
        return output.read().decode('ascii').strip("\n")

    def _GetPlatform(self):
        for t, cmd in self.platformCommands.items():
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd)
                err = self.__decodeSSHCommandOutput(stderr)
                if err:
                    logging.info("Not {} platform".format(t))
                else: self.platform = t
            except Exception as e:
                logging.error(e)
                raise(e)
        if not self.platform:
            msg = "Could not find platform for the config. Couldn't execute command"
            logging.error(msg)
            raise(Exception(msg))
        return(self.platform)

    def _MD5ToJSON(self, raw, relPath):
        out = []
        lines = raw.split("\n")
        for line in lines:
            md5, path = line.split(" *")
            path = path.removeprefix(relPath)
            out.append(HashDict(md5, path))
        return out

    def CheckIfFileExists(self, path):
        try:
            self.sftp.stat(path)
            return True
        except: return False


    ### REMOTE HASH BLOCK ###
    """
    ## We want to avoid repetition, however... Windows is a little f up with hashing.
    I cannot pass multiple files without doing custom script,
    Also Powershell or CMD ? 2 Diff commands :/
    I can use Custom scripts... Cause Powershell
    Also Win Server needs to support Powershell as def...
    For sanity purpose let's stay on one file -> One hash
    Not efficient for now, but it will pass
    """
    def GetHash(self,path, hashtype: str = "md5"):
        cmd = (self.__GetMd5HashCMD(platform=self.platform)).format(path)
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd)
            out = self.__decodeSSHCommandOutput(stdout)
        except Exception as e:
            logging.error(e)
            raise(e)
        return out

    def GetStat(self, path):
        targetStat = None
        try:
            targetStat = self.sftp.stat(path)
        except Exception as e:
            logging.error("Target Doesnt Exist: {}".format(path))
            logging.error(e)
        return targetStat

    ### REMOTE SyncTask BLOCK ###
    def CreateSyncTask(self, syncObj, originalPath=None):
        remoteList = []
        ## Should be in ConfigLoader :/
        self._ValidationMirrorTargetPath(syncObj=syncObj)
        statAttr = self.GetStat(syncObj.GetRemotePath())
        if type(statAttr) == sftp_attr.SFTPAttributes:
            if self._IsDir(statAttr.st_mode):
                syncObj.isDir = self._IsDir(statAttr.st_mode)
                remoteList.extend(self.__GetSyncPathRemoteFolder(syncObj))
            else:
                remoteList.append(syncObj)
        return remoteList

    def __GetSyncPathRemoteFolder(self, syncObj, returnDir=True):
        filesList = []
        dirAttr = self.sftp.listdir_attr(syncObj.GetRemotePath())
        for targetAtt in dirAttr:
            relRemotePath = syncObj.GetRemotePath() + targetAtt.filename
            isDir = self._IsDir(targetAtt.st_mode)
            slash = self.GetSystemSlash(self.platform) if isDir else ""
            syncTask = self._CombineMirrorAndTarget(
                foundPath=relRemotePath + slash,
                fillPath=syncObj.GetLocalPath(),
                originaRemotelFolder=syncObj.GetRemotePath(),
                remoteMirror=syncObj.remoteMirror,
                isDir=isDir,
            )
            if isDir:
                if returnDir:
                    filesList.append(syncTask)
                filesList.extend(self.__GetSyncPathRemoteFolder(syncTask))
            else: filesList.append(syncTask)
        return filesList

    ### REMOTE CREATE BLOCK ###
    def CreateFolder(self):
        pass

    def CreateFile(self):
        pass

    ### REMOTE REMOVE BLOCK ###
    def RemoveTarget(self, path, isDir=False):
        if self.CheckRemoveSafePaths(path):
            if self.CheckIfFileExists(path):
                if isDir:
                    self._RemoveFolder(path)
                else:
                    self._RemoveFile(path)
            else:
                msg = "Remote file/directory doesn't exist: {}".format(path)
                logging.info(msg)
        else:
            msg = "Error Unsafe path {}".format(path)
            raise msg

    def _RemoveFolder(self, path):
        # I might be Paranoid, but i know that once i will forget it
        # And i'm going to delete system.
        if self.CheckRemoveSafePaths(path):
            listDir = self.sftp.listdir(path)
            if listDir:
                for toDelete in listDir:
                    logging.info("Found new path \'{}\' in folder {}".format(toDelete, path))
                    stat = self.sftp.stat(path)
                    isDir = self._IsDir(stat.st_mode)
                    self.RemoveTarget(toDelete, isDir=isDir)
            self.sftp.rmdir(path)
        else:
            msg = "ERROR: Found unsafe path somehow passed check {}".format(path)
            logging.error(msg)
            raise msg

    def _RemoveFile(self, path):
        if self.CheckRemoveSafePaths(path):
            self.sftp.remove(path)
        else:
            msg = "ERROR: found unsafe path, somehow passed check {}".format(path)
            logging.error(msg)
            raise msg

    def GetHashMd5(self, syncObj) -> str:
        out = ""
        path = syncObj.GetRemotePath()
        cmd = str(self.GetMd5HashCMD(self.platform)).format(path)
        if self.CheckIfFileExists(path):
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd)
                out = self.__decodeSSHCommandOutput(stdout)
            except:
                pass
        return out


class LocalFilesAndDirs(OSCmd,  __CommonManagement):
    def __init__(self):
        super().__init__()
        self.__SetPlatform()

    def __SetPlatform(self):
        result = None
        logging.info("Attempting Finding Local Platform Type")
        for t, cmd in self.platformCommands.items():
            try:
                result = subprocess.run(cmd, capture_output=True)
                self.platform = t
            except Exception as e:
                logging.error(e)
            if self.platform:
                logging.info("Found Local platform: {}".format(t))
                break
        if not self.platform:
            msg = "Could not find Local platform for the config. Couldn't execute command"
            logging.error(msg)
            raise (Exception(msg))

    def ReadJSONFile(self, path):
        try:    
            return json.load(open(path))
        except IOError as e:
            logging.error("File not Found")
            raise(e)
        except json.decoder.JSONDecodeError as e:
            logging.error("JSON File is incorrectly formated or empty {}".format(path))
            raise(e)
        

    def AppendToFile(self, path, data):
        try:
            with open(path,"a") as f:
                f.write(data)
        except IOError as e:
            msg= "Could not append to file with {}".format(path)
            logging.error(msg, e)
            raise e
        except Exception as e:
            msg= "Unexpected error has occurred with{}".format(path)
            logging.error(msg)
            raise e

    def CheckIfFileExists(self, path):
        return os.path.exists(path)

    ### LOCAL HASH BLOCK ###
    def GetHashMd5(self, syncObj, hashtype="md5"):
        hashed = ""
        path = syncObj.GetLocalPath()
        if os.path.isfile(path):
            with open(path, "r") as f:
                hashed = self.__HashMd5(f.read())
        return hashed

    def __HashMd5(self, text):
        return hashlib.md5(text.encode()).hexdigest()

    ### LOCAL SyncTask CREATION ###
    def CreateSyncTaskList(self, taskObj):
        taskList = []
        localPath = taskObj.GetLocalPath()
        if os.path.isfile(localPath):
            taskObj.isDir = False
            taskList.append(taskObj)
        else:
            taskObj.isDir = True
            taskList.extend(self._GetListSyncTaskFromFolder(taskObj=taskObj, originalPath=taskObj.GetLocalPath()))
        return taskList

    def _GetListSyncTaskFromFolder(self, taskObj, originalPath=""):
        pathList=[]
        for entry in os.scandir(taskObj.GetLocalPath()):
            statAttr = os.stat(entry)
            isDir = self._IsDir(statAttr.st_mode)
            slash = self.GetSystemSlash(self.platform) if isDir else ""
            filename = entry.path.removeprefix(originalPath)
            if taskObj.remoteMirror:
                syncObj = SyncTask(
                    remoteMirror=taskObj.remoteMirror,
                    mirrorPath=taskObj.mirrorPath + filename + slash,
                    targetPath=entry.path + slash,
                    isDir= isDir,
                )
            else:
                syncObj = SyncTask(
                    remoteMirror=taskObj.remoteMirror,
                    mirrorPath=entry.path + slash,
                    targetPath=taskObj.targetPath + filename + slash,
                    isDir=isDir,
                )

            #logging.info("To Local Sync List added new file {}".format(syncObj.GetLocalPath()))
            if syncObj.isDir:
                pathList.append(syncObj)
                pathList.extend(self._GetListSyncTaskFromFolder(syncObj, originalPath=syncObj.GetLocalPath()))
            else: pathList.append(syncObj)
        return pathList

    ### LOCAL CREATE BLOCK ###
    def CreateFolder(self, path):
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
                logging.info("Created Directory at {}".format(path))
            except IOError as e:
                msg = "Could not create Directory at {}".format(path)
                logging.error(msg, e)
                raise e
            except Exception as e:
                msg = "Unexpected error has occurred at{}".format(path)
                logging.error(msg)
                raise e
        else:
            msg = "Folder exists {}, skipping".format(path)
            logging.info(msg)

    def CreateFile(self, path):
        try:
            with open(path, "w") as f:
                pass
        except IOError as e:
            msg = "Could not create file with {}".format(path)
            logging.error(msg, e)
            raise e
        except Exception as e:
            msg = "Unexpected error has occurred with{}".format(path)
            logging.error(msg)
            raise e

    ### LOCAL REMOVE BLOCK ###
    def RemoveTarget(self, syncTask, isDir=False):
        path = syncTask.GetLocalPath()
        if self.CheckRemoveSafePaths(path):
            if syncTask.isDir:
                self._RemoveFolder(path)
            else:
                self._RemoveFile(path)
        else:
            msg = "Error Unsafe path {}".format(syncTask.toDict())
            raise msg

    def _RemoveFolder(self, path):
        # I might be Paranoid, but i know that once i will forget it
        # And i'm going to delete system.
        if self.CheckRemoveSafePaths(path):
            shutil.rmtree(path)
        else:
            msg = "ERROR: Found unsafe path somehow passed {}".format(path)
            logging.error(msg)
            raise msg

    def _RemoveFile(self, path):
        if self.CheckRemoveSafePaths(path):
            os.remove(path)
        else:
            msg = "ERROR: Found unsafe path {}".format(path)
            logging.error(msg)
            raise msg

class ConfigLoader(LocalFilesAndDirs):
    def __init__(self):
        super().__init__() 
    
    def _RandomName(self):
        self.name = self.__HashMd5(str(datetime.now().timestamp()))

    def AddMissingFolders(self):
        folders = [self.configFolder, self.keysFolder]
        for path in folders:
            self.CreateFolder(path) 

    def GenerateClientConfig(self, hostname:str, mirrorPath:str, targetPath:str,
                             user:str ,configName:str, timeout:int, passwordReq: bool = True, keyPath:str="", remoteMirror=True,
                             isDir=False, toFile = False, cleanTransfer=False):

        if configName and toFile:
            configName = self._ValidateClientConfigName(configName, toFile=False)
            configPath = self.configFolder + configName
        elif not configName :
            configPath = ""
            configName = self._RandomName()
        else: configPath = ""
        pwd = self.InputPassword() if passwordReq else ""

        cfg = ClientConfig(
            syncType="ZeroToOne",
            passwordReq=passwordReq,
            configPath= configPath,
            configName = configName,
            user = user,
            pwd = pwd,
            keyPath = keyPath,
            hostname = hostname,
            cleanTransfer= cleanTransfer,
            paths = [SyncTask(
                remoteMirror=remoteMirror,
                mirrorPath=mirrorPath,
                targetPath=targetPath,
                isDir=isDir)]
        )
        # less fun until i don't have autosyncing no need for creating object.
        cfg.times["timeout"] = timeout
        if toFile:
            self.CreateFile((self.configPath) + ".json")
        return cfg
    
    def InputPassword(self):
        pwd = getpass("Please enter password to Instance: ")
        return pwd

    def CheckIfConfigFolderExists(self) -> bool:
        b = os.path.isdir(self.configFolder)
        if b: logging.info("Config Folder Exists? {}, at {}".format(b,self.configFolder))
        return b

    def CheckIfGlobalConfigExists(self) -> bool:
        b = os.path.isfile(self.globalConfig)
        logging.info("Global Config File Exists? {}, at {}".format(b, self.globalConfig))
        return b

    def CreateConfigFolder(self) -> bool:
        if not self.CheckIfConfigFolderExists():
            logging.info("Creating conf folder {}".format(self.configFolder))
            os.mkdir(self.configFolder)
            return True
        return False
        
    def GenerateGlobalConfig(self) -> bool:
        if not self.CheckIfGlobalConfigExists():
            return True
        return False
    
    def LoadGlobalConfig(self) -> GlobalConfig :
        data = self.ReadJSONFile(path=self.globalConfig)
        try:
            globalConfiguration = GlobalConfig(**data, configPath=self.globalConfig)
        except TypeError as te:
            logging.error("Global Configuration file seems to have incorrect names or values. Error msg {e}")
            raise te

        logging.info("Global Configuration has been successfully loaded. \n\t{}".format(globalConfiguration) )
        return globalConfiguration
    
    def _ValidateClientConfigName(self, name, asFile=True):
        if not type(name)==str:
            msg = "Received empty string or different type"
            logging.error(msg)
        name, ext = os.path.splitext(name)
        if asFile and ext=='.json':
            return str(name + ext)
        elif asFile and not ext=='.json':
            return str(name + '.json')
        else: return name
            
    def _GetClientConfigFileNames(self):
        try:
            f = [file for file in os.listdir(self.configFolder) if os.path.isfile(os.path.join(self.configFolder, file)) and file.endswith('.json')]
            logging.info("Found Client Configs: {}".format(f))
        except Exception as e:
            logging.error("Something went wrong during Client files lookup {}".format(e))
        return f
    
    def LoadAllClientConfigs(self, excludedFiles:list = []) -> list:
        excludedNames = [f.strip('.json') for f in excludedFiles]
        excludedNames.append("global")
        clientNames = set([f.strip('.json') for f in self._GetClientConfigFileNames()]) - set(excludedNames)
        clients=[]
    
        for name in clientNames:
            path = self.configFolder + name + ".json"
            clients.append(self.LoadClientConfig(path))
        return clients

    def LoadClientConfig(self, configLoc):
        try:
            name = self._ValidateClientConfigName(os.path.basename(configLoc), asFile=False)
            data = self.ReadJSONFile(path=configLoc)
            data["paths"] = [SyncTask(remoteMirror= x["remoteMirror"], mirrorPath=x["mirrorPath"], targetPath=x["targetPath"]) for x in data["paths"]]
            return ClientConfig(**data, configName=name, configPath=configLoc)
        except TypeError as te:
            logging.error("Configuration Client {} file seems to have incorrect names or values. Error msg {}".format(name, te))
            raise(te)
        except Exception as e:
            logging.error("Unexpected Error has occurred {}".format(e))
            raise e