import os
import shutil
import json
import logging

from pathlib  import Path
from dotenv import load_dotenv
from json import JSONEncoder
from datetime import datetime
from getpass import getpass

from lib.dataformats import *


print("Is dotenv:" + str(load_dotenv()))

logging.basicConfig(level=logging.DEBUG)

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
        self.platformCommands = {"MacOS":'sw_vers', "Linux": 'uname', "Win":'ver'}
        self.md5 = {"Linux": "md5sum -b", "Win": "", "MacOS": "md5"}
        self.osdictPath = self.libFolder + "osdict.json"
        self.osdict = None
        self._GetOsDict()

    def _GetOsDict(self):
        with open(self.osdictPath) as f:
            self.osdict = json.load(f) 


class RemoteFilesAndDirs(OSCmd):
    def __init__(self, client):
        super().__init__() 
        self.client = client
        self._SetPlatform()

    def _SetPlatform(self):
        for t, cmd in self.platformCommands.items():
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd)
                err = self._decodeSSHCommandOutput(stderr)
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

    def _LoadConfigJson(self):
        pass

    def _decodeSSHCommandOutput(self,output):
        return output.read().decode('ascii').strip("\n")

    def GetPlatform(self):
        for t, cmd in self.platformCommands.items():
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd)
                err = self._decodeSSHCommandOutput(stderr)
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
        

    def HashOut(self, path, relPath, raw=False):
        if type(path) == list:
            path = " ".join(str(x) for x in path)
        try: 
            cmd = self.md5[self.platform] + " " + path
            stdin, stdout, stderr = self.client.exec_command(cmd)
            out = self._decodeSSHCommandOutput(stdout)
        except Exception as e:
            logging.error(e)
            raise(e)
        if not raw:
            out = self._MD5ToJSON(out, relPath)
        return out


class LocalFilesAndDirs(OSCmd):
    def ReadJSONFile(self, path):
        try:    
            return json.load(open(path))
        except IOError as e:
            logging.error("File not Found")
            raise(e)
        except json.decoder.JSONDecodeError as e:
            logging.error("JSON File is incorrectly formated or empty {}".format(path))
            raise(e)
        
    def CreateFolder(self, path):
        if not os.path.isdir(path):
            print(path)
            try:    
                os.mkdir(path)
                logging.info("Created Directory at {}".format(path))
            except IOError as e:
                msg= "Could not create Directory at {}".format(path)
                logging.error(msg, e)
                raise e
            except Exception as e:
                msg= "Unexpected error has occured at{}".format(path)
                logging.error(msg)
                raise e
        else:
            msg = "Folder exists {}, skipping".format(path)
            logging.info(msg)

    def CreateFile (self, path):
        try:
            with open(path,"w") as f:
                f.write(data)
        except IOError as e:
            msg = "Could not create file with {}".format(path)
            logging.error(msg, e)
            raise e
        except Exception as e:
            msg = "Unexpected error has occured with{}".format(path)
            logging.error(msg)
            raise e
    
    def AppendToFile(self, path, data):
        try:
            with open(path,"a") as f:
                f.write(data)
        except IOError as e:
            msg= "Could not append to file with {}".format(path)
            logging.error(msg, e)
            raise eb
        except Exception as e:
            msg= "Unexpected error has occured with{}".format(path)
            logging.error(msg)
            raise e

    def _CheckRemoveSafePaths(path):
        if not path in self.unsafePaths:
            return True
        return False

    def _CheckIfFileExists(self, path):
        return os.path.exists(path)

    def RemoveTarget(self, syncTask, isDir=False):
        path = syncTask.GetLocalPath()
        if self._CheckRemoveSafePaths(path):
            if isDir: _RemoveFolder(path)
            else: _RemoveFile(path)
        else: 
            msg = "Error Unsafe path {}".format(syncTask.__dict__)
            raise msg

    def _RemoveFolder(self, path):
        # I might be Paranoid, but i know that once i will forget it
        # And i'm going to delete system. 
        if self._CheckRemoveSafePaths(path):
            shutil.rmtree(path)
        else:
            msg = "ERROR: Found unsafe path somehow passed {}".format(path)
            logging.error(msg)
            raise msg
    
    def _RemoveFile(self, path):
        if self._CheckRemoveSafePaths(path):
            os.remove(path)
        else:
            msg = "FERROR: ound unsafe path {}".format(path)
            logging.error(msg)
            raise msg

    def LocalHashMd5(self, text):
        return hashlib.md5(text.encode()).hexdigest()

class ConfigLoader(LocalFilesAndDirs):
    def __init__(self):
        super().__init__() 
    
    def _RandomName(self):
        self.name = self.LocalHashMd5(str(datetime.now().timestamp()))

    def AddMissingFolders(self):
        folders = [self.configFolder, self.keysFolder]
        for path in folders:
            self.CreateFolder(path) 

    def GenerateClientConfig(name:str, hostname:str, mirrorPath:str, targetPath:str, user:str ,passwordReq: bool = True, keyPath:str="", remoteMirror=True, isDir=False, toFile = False):
        if name and toFile:
            name = _ValidateClientConfigName(filename, toFile=False )
            configPath = self.configFolder + name
        else: cofigPath = ""
        pwd = getpass("Please enter password to Instance: ")
        cfg = ClientConfig(
            syncType="ZeroToOne",
            passwordReq=True,
            configPath= cofigPath,
            configName = name,
            user = user,
            pwd = pwd,
            keyPath = keyPath,
            hostname = hostname,
            paths = SyncTask(remoteMirror=remoteMirror, mirrorPath=mirrorPath, targetPath=targetPath, isDir=isDir)
        )
        if toFile:
            self.CreateFile(self.configPath)
        return cfg

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

        logging.info("Global Configuration has been succesfuly loaded. \n\t{}".format(globalConfiguration) )
        return globalConfiguration
    
    def _ValidateClientConfigName(self, name, asFile=True):
        if not type(name)==str:
            msg = "Recived empty string or different type"
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
            print(name)
            data = self.ReadJSONFile(path=configLoc)
            data["paths"] = [SyncTask(remoteMirror= x["remoteMirror"], mirrorPath=x["mirrorPath"], targetPath=x["targetPath"]) for x in data["paths"]]
            return ClientConfig(**data, configName=name, configPath=configLoc)
        except TypeError as te:
            logging.error("Configuration Client {} file  seems to have incorrect names or values. Error msg {}".format(name, te))
            raise(te)