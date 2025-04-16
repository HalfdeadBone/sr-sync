import paramiko
from datetime import datetime
import os
import json
import stat
import logging
import hashlib
import lib.dataformats as dataformats
from lib.files import LocalFilesAndDirs, RemoteFilesAndDirs
from lib.dataformats import PathDict, HashDict, SyncTask

class SimpleSSHClient:
    paramiko.util.log_to_file("paramiko.log")
    def __init__(self, config=None, user=None, hostname=None):
        self.session = paramiko.SSHClient()
        self.sftp = None
        self.name = None
        self.hostname = hostname
        self.user = user
        self.pwd = ""
        self.config = config
        self.LocalManagment = LocalFilesAndDirs() #Platform Inside
        #After Basic Values
        self._SetConfigValues()
        self._ConnectToHost() #Set client
        
        # Init Remote Managment and set platform for it
        self.RemoteManagment = RemoteFilesAndDirs()
        self._RemotePlatform(client= self.client, sftp = self.sftp)

    def _SetConfigValues(self):
        if self.config:
            self.hostname = self.config.hostname
            self.user = self.config.user
            self.key = self.config.keyPath if self.config.keyPath else None
            self.pwd = self.config.pwd

    def _ConnectToHost(self):
        # we coooould use Context... Note for later
        self._ValidationPreConnection(
            {"hostname": self.hostname, "user": self.user}, name=self.name
        )
        self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.session.connect(
                hostname=self.hostname,
                username=self.user,
                password=self.pwd,
                key_filename=self.key,
            )
            logging.info("Connected via SSH to '{}'".format(self.name))
        except Exception as e:
            raise AttributeError(e)

    def _RemotePlatform(self, pathList, relPath):
        self.RemoteManagment.GetPlatform()

    ### IDEA VALIDATION OF CONFIG SHOULD RETURN error type + MSG
    ### THEN FULL _ValidateConfig should be created
    ### Then Move it to ConfigLoader

    def _ValidationIsMirrorPathNotEmpty(self, syncTask, codeName):
        msg = None
        if not SyncTask.GetRemotePath():
            msg = "Mirror path is not set for {} in: {}".format(
                codeName, syncTask.__dict__
            )

    def _ValidationPreConnection(self, dictToValidate, name):
        missingVal = []
        for key, val in dictToValidate.items():
            if val == None:
                missingVal.append(key)
        if missingVal:
            msg = "Found missing variables for {} in 'paths': {}".format(
                name, dictToValidate
            )
            logging.error(msg)
            raise TypeError(msg)

    def _IsDir(self, st_mode: str):
        return stat.S_ISDIR(st_mode)

    def _GetSyncPathRemoteFolder(self, syncObj, returnDir=True):
        filesList = []
        dirAttr = self.sftp.listdir_attr(syncObj.GetRemotePath())
        for targetAtt in dirAttr:
            relRemotePath = syncObj.GetRemotePath() + targetAtt.filename
            isDir = self._IsDir(targetAtt.st_mode)
            slash = "/" if isDir else ""
            syncTask = self._CombineMirrorAndTarget(
                foundPath=relRemotePath + slash,
                fillPath=syncObj.GetLocalPath(),
                originalRemoteFolder=syncObj.GetRemotePath(),
                remoteMirror=syncObj.remoteMirror,
                isDir=isDir,
            )
            if isDir:
                if returnDir:
                    filesList.append(syncTask)
                filesList.extend(self._GetSyncPathRemoteFolder(syncTask))
            elif relRemotePath:
                filesList.append(syncTask)
            else:
                continue
        return filesList

    def _StatSyncPathRemote(self, syncObj):
        pathAttr = self.sftp.stat(syncObj.GetRemotePath())
        if type(pathAttr) == paramiko.sftp_attr.SFTPAttributes:
            syncObj.isDir = self._IsDir(pathAttr.st_mode)
            return syncObj
        else:
            return None

    def _CombineMirrorAndTarget(
        self, foundPath, fillPath, remoteMirror, originalRemoteFolder, isDir
    ):
        """
        Returns proper SyncTask configure to account "remoteMirror" value.
        """
        if remoteMirror:
            return SyncTask(
                remoteMirror=remoteMirror,
                mirrorPath=foundPath,
                targetPath=fillPath + foundPath.removeprefix(originalRemoteFolder),
                isDir=isDir,
            )
        else:
            relPath = foundPath.removeprefix(originalRemoteFolder)
            return SyncTask(
                remoteMirror=remoteMirror,
                mirrorPath=fillPath + foundPath.removeprefix(originalRemoteFolder),
                targetPath=foundPath,
                isDir=isDir,
            )


    def EstablishSftp(self):
        self._ConnectToHost()
        self.sftp = self.session.open_sftp()

    def ReSyncListOfSyncTask(self, syncTaskList):
        #syncTaskList change to self.LastTaskList, allows to just call last sync
        a = self.config.GetPathList()
        fresh = [data for data in self._GetListSyncPathRemoteFiles(a[0])]

        oldSync = set([json.dumps(x.__dict__) for x in syncTaskList])
        newSync = set([json.dumps(x.__dict__) for x in fresh])
        toMove = None
        toRemove = None

        if not oldSync == newSync:
            toMove = oldSync & newSync
            toRemove = oldSync - newSync
            toMove = [SyncTask(**json.loads(x)) for x in toMove]
            toRemove = [SyncTask(**json.loads(x)) for x in toRemove]

        newSync = [SyncTask(**json.loads(x)) for x in newSync]
        #newSync needs to be verify via HASH, so here should be method for that
        # it would need to return list of task sync, after pathDicts
        # for now no hashing always download all
        return toMove, toRemove, newSync

    def _GetRelPath(self, pathA: str, pathB: str, isDir=False):
        pathA = pathA.split("/")
        pathB = pathB.split("/")
        subDir = []
        #
        for i in range(len(pathA)):
            if pathA[i] == pathB[i]:
                subDir.append(pathA[-i])
            else:
                break
        subDir.reverse()
        # if isDir: subDir.pop(0)
        return "/".join(x for x in subDir)

    def GetRemoteListPathDict(
        self, syncList, originalPath=None, remote=True, ignoreDir=True
    ) -> list:
        """
        Creates list of objects: PathDict, that represents local and remote connection, for future Hash keeping
        to verify versions of files. 

        :param syncList     :List of Syncronized objects: SyncTask, represening Task
        :param originalPath :String containing original remote path, before reentering. Set by method
        :param remote       :checks if Mirror is remote (not used for now)
        :param ignoreDir    :Bool representing if Dir should be added to finalList

        :returns: List[PathDict] or empty list
        """

        finalList = []
        for syncObj in syncList:
            if ignoreDir and syncObj.isDir:
                continue
            else:
                pathDict = self._GetRemotePathDict(
                    syncObj=syncObj, originalPath=originalPath, ignoreDir=ignoreDir
                )
                if pathDict:
                    finalList.append(pathDict)
        return finalList

    def _GetRemotePathDict(
        self,
        syncObj,
        ignoreDir,
        originalPath=None,
    ):
        if not originalPath:
            originalPath = syncObj.GetRemotePath()
        targetStat = self.RemoteManagment.GetStat(syncObj.GetRemotePath())
        if targetStat:
            if self._IsDir(targetStat.st_mode) and ignoreDir:
                return None
            else:
                filename = syncObj.GetFilename() if not syncObj.isDir else None
                relPath = syncObj.GetRemotePath().removeprefix(originalPath)
                return PathDict(
                    **syncObj.__dict__,
                    subDir=relPath.removesuffix(filename)
                    if not syncObj.isDir
                    else relPath,
                    filename=filename,
                    st_mode=targetStat.st_mode,
                    st_mtime=targetStat.st_mtime,
                    relPath=relPath,
                )
        return None

    def _HashMd5(self, text):
        return hashlib.md5(text.encode()).hexdigest()

    def _LocalHash(self, pathList, relPath) -> list:
        # zrób dla jednego
        hashList = []
        for path in pathList:
            with open(path, "r") as f:
                h = self._HashMd5(f.read())
                hashList.append(HashDict(hash=h, relPath=path.removeprefix(relPath)))
        return hashList

    def GetHash(self, relPath, pathList, remote=True):
        if remote:
            return self._RemoteSSHHash(pathList=pathList, relPath=relPath)
        else:
            return self._LocalHash(pathList=pathList, relPath=relPath)

    def OpenTarget(self, path, mode="r", bufsize=-1):
        target = None
        try:
            target = self.sftp.file(filename=path, mode=mode, bufsize=bufsize)
        except IOError as e:
            print(e)
        return target

    def CheckSum(self, a, b) -> bool:
        return self._HashMd5(a) == self._HashMd5(b)
    
    def DownloadChosenTarget(self, syncObj):
        """
        Downloads From Mirror to Target
        """
        if syncObj.isDir and not os.path.exists(syncObj.GetLocalPath()):
            self.LocalManagment.CreateFolder(path=syncObj.GetLocalPath())
        if syncObj.filename:
            self.sftp.get(
                localpath=syncObj.GetLocalPath(), remotepath=syncObj.GetRemotePath()
            )
            logging.info("Downloaded file: {}".format(syncObj.GetLocalPath()))

    def GetSyncTaskList(self, taskList):
        syncList = []
        for taskObj in taskList:
            if taskObj.remoteMirror: syncList.append(**self.RemoteManagment.CreateSyncTask(taskObj))
            else: syncList.append(**self.fLocalFilesAndDirs.CreateSyncTask(taskObj))
        return syncList

    def PutChosenTarget(self, syncObj):
        if syncObj.isDir and not self.sftp.stat(syncObj.GetRemotePath()):
            self.sftp.mkdir(syncObj.GetRemotePath())
        self.sft.put(
            localpath=syncObj.GetLocalPath(), remotepath=syncObj.GetRemotePath()
        )
        logging.info("Downloaded file: {}".format(syncObj.GetRemotePath()))

    def UpdatePathsWithHash(self, pathDictList):
        pass

    def MoveAction(self, syncObj):
        if not syncObj.remoteMirror:
            self.DownloadChosenTarget(syncTask=syncObj)
        elif syncObj.remoteMirror:
            self.PutChosenTarget(SyncTask=syncObj)

    def RemoveAction(self, syncObj):
        # if remoteMirror ==  True, them remove and make in local 
        if syncObj.remoteMirror:
            self.LocalManagment.RemoveTarget(syncTask=syncObj)
        # if not remoteMirror == False, means we are deleting remote files 
        elif not syncObj.remoteMirror:
            self.RemoteManagment.RemoveTarget(SyncTask=syncObj)
            

    def ExecuteAction(self, action, actionType='move'):
        if actionType== 'remove':
            self.RemoveAction()
        elif actionType == 'move':
            pass
        else:
            msg = "Recived unknown Action".format(actionType)
            logging.error()

    def ExecuteSync(self, toRemove: list[SyncTask], toMove: list[SyncTask]):
        for syncObj in toRemove:
            self.ExecuteAction(syncObj=syncObj,actionType='remove')
        for syncObj in toMove:
            self.ExecuteAction(syncObj=syncObj,actionType='move')