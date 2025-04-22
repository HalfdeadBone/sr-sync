from dataclasses import dataclass, field
from copy import copy

@dataclass
class _ToJSON():
    def ToJSON(self):
        return(self.__dict__)


## To fix situation remote2remote create alternative
# BaseConfig where hostname could be applied 
@dataclass
class SyncTask:
    remoteMirror: bool = True
    mirrorPath: str = ""
    targetPath: str = ""
    isDir:bool = False

    def GetSubDirFromRemotePath(self, originalPath):
        if self.remoteMirror: return copy(self.mirrorPath).removeprefix(originalPath)
        else: return copy(self.targetPath).removeprefix(originalPath)

    def GetRemotePath(self):
        if self.remoteMirror: return self.mirrorPath
        else: return self.targetPath
    
    def GetLocalPath(self):
        if self.remoteMirror: return self.targetPath
        else: return self.mirrorPath
    
    def GetFilename(self):
        if self.isDir: return None
        split = self.GetRemotePath()
        return copy(str(split).split("/")[-1])

    def toDict(self):
        return self.__dict__

@dataclass(slots=True)
class PathDict(SyncTask):
    filename: str = ""
    subDir:str = ""
    relPath: str = ""
    st_mode: str = ""
    st_mtime: str = ""
    targetHash: str = ""
    mirrorHash: str = ""
    
    def UpdateRelPath(self):
        self.relPath = self.subDir + self.filename
        return self.relPath


@dataclass(slots=True) 
class _TimesData:
    timeout: int = 180
    timeInterval: int = 20
    timeOveride: bool = False
    
    def ConfigTimings(self):
        print({"Global Timeout": self.timeout, "Sync Intervals": self.timeInterval, "Overide of timings": self.timeOveride}) 

@dataclass(slots=True) 
class DataConfig:
    syncType: str 
    passwordReq: bool 
    configPath: str = ""
    times: _TimesData = _TimesData

    def toDict(self):
        return self.__dict__

@dataclass(slots=True,init=True)
class ClientConfig(DataConfig):
    hostname: str = ""
    configName: str = ""
    user: str = ""
    keyPath: str = ""
    pwd:str = ""
    paths: list[SyncTask] = field(default_factory=list[SyncTask])
    errorPaths: list[str] = field(default_factory=list)
     
    def ConfigLocation(self):
        print({"Config name": self.name, "Config Path": self.configPath})

    def GetPathList(self):
        return self.paths


@dataclass(slots=True) 
class GlobalConfig(DataConfig):
    excludedNames: list[str] = field(default_factory=list)

    def ExcludedConfigs(self):
        print({"Config Name": self.name, "Excluded Configs": self.excludedNames})

@dataclass
class HashDict():
    """
    Create hashmap with relative path
    :param hash: chosen hash
    :param relPath: relative Path to file
    """
    hash:str
    relPath:str 
    
    def GetHashLine(self):
        return str(self.hash + " " + self.relPath) 
