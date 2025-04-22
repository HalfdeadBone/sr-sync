import paramiko

import os
import json
import stat
import logging
import hashlib
from copy import copy

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
        self.RemoteManagment = RemoteFilesAndDirs(client = self.session, sftp=self.sftp)
        #self._RemotePlatform() #disabled

    def _SetConfigValues(self):
        if self.config:
            self.name =  self.config.configName
            self.hostname = self.config.hostname
            self.user = self.config.user
            self.key = self.config.keyPath if self.config.keyPath else None
            self.pwd = self.config.pwd


    def _ValidationPreConnection(self, dictToValidate, name):
        logging.info("Validating if all items are added")
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


    def _ConnectToHost(self):
        # we coooould use Context... Note for later
        self._ValidationPreConnection(
            {"hostname": self.hostname, "user": self.user}, name=self.name
        )
        self.session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            logging.info("Attempting to Connect via SSH to '{}'".format(self.name))
            self.session.connect(
                hostname=self.hostname,
                username=self.user,
                password=self.pwd,
                key_filename=self.key,
                timeout=self.config.times["timeout"]
            )
            logging.info("Connected via SSH to '{}'".format(self.name))
            self.sftp = self.session.open_sftp()
        except Exception as e:
            raise e

    def _RemotePlatform(self):
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

    def _IsDir(self, st_mode: str):
        return stat.S_ISDIR(st_mode)


    def ReSyncListOfSyncTask(self, syncTaskList, originalSyncTask: SyncTask):
        #syncTaskList change to self.LastTaskList, allows to just call last sync

        # Logic -> Our "past" Experience is target folder/file in original task.
        # If so. All I have to do is pass to function old data and ingnore Check for
        # if remoteMirror, but keep it. Thanks to set hasing if they are the same,
        # it will be popped / move to different task.
        if originalSyncTask.remoteMirror:
            fresh = [data for data in self.LocalManagment.CreateSyncTaskList(originalSyncTask)]
        else:
            fresh = [data for data in self.RemoteManagment.CreateSyncTask(originalSyncTask)]

        oldSync = set([json.dumps(x.toDict()) for x in copy(syncTaskList) if x])
        newSync = set([json.dumps(x.toDict()) for x in copy(fresh) if x])

        toMove = None
        toRemove = None
        toCreate = None

        #print(oldSync)
        #print (fresh)
        if oldSync != newSync:
            toRemove = newSync - oldSync
            toMove = oldSync - newSync
            toRemove = [SyncTask(**json.loads(x)) for x in toRemove]

            toMove = [SyncTask(**json.loads(x)) for x in toMove]
            toCreate = [x for x in toMove if x.isDir]

        targetSync = fresh
        #newSync needs to be verify via HASH, so here should be method for that
        # it would need to return list of task sync, after pathDicts
        # for now no hashing always download all
        return toMove, toCreate, toRemove, targetSync

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
            logging.info(e)
        return target

    def CheckSum(self, a, b) -> bool:
        return self._HashMd5(a) == self._HashMd5(b)
    
    def DownloadChosenTarget(self, syncObj):
        """
        Downloads From Mirror to Target
        """
        if syncObj.isDir:
            if not os.path.exists(syncObj.GetLocalPath()):
                self.LocalManagment.CreateFolder(path=syncObj.GetLocalPath())
        else:
            self.sftp.get(
                localpath=syncObj.GetLocalPath(), remotepath=syncObj.GetRemotePath()
            )
            logging.info("Downloaded file: {}".format(syncObj.GetLocalPath()))

    def GetSyncTaskList(self, taskList):
        syncList = []
        for taskObj in taskList:
            if taskObj.remoteMirror:
                val = self.RemoteManagment.CreateSyncTask(taskObj)
                syncList.extend(val)
            else: syncList.extend(self.LocalManagment.CreateTaskList(taskObj))
        return syncList

    def PutChosenTarget(self, syncObj):
        if syncObj.isDir:
            if not self.sftp.stat(syncObj.GetRemotePath()):
                self.sftp.mkdir(syncObj.GetRemotePath())
        else:
            self.sftp.put(
                localpath=syncObj.GetLocalPath(), remotepath=syncObj.GetRemotePath()
            )
            logging.info("Downloaded file: {}".format(syncObj.GetRemotePath()))

    def UpdatePathsWithHash(self, pathDictList):
        pass


    ### ACTION BLOCK ###
    def MoveAction(self, syncObj):
        if syncObj.remoteMirror:
            self.DownloadChosenTarget(syncObj=syncObj)
        elif not syncObj.remoteMirror:
            self.PutChosenTarget(syncObj=syncObj)

    def RemoveAction(self, syncObj):
        logging.warning("Deleting: {}".format(syncObj.GetLocalPath()))
        if  syncObj.remoteMirror:
            self.LocalManagment.RemoveTarget(syncTask=syncObj)
        elif not syncObj.remoteMirror:
            self.RemoteManagment.RemoveTarget(path=syncObj.GetRemotePath())
            
    def CreateAction(self, syncObj):
        if syncObj.remoteMirror:
            self.DownloadChosenTarget(syncObj=syncObj)
        elif not syncObj.remoteMirror:
            self.PutChosenTarget(syncObj=syncObj)

    def ExecuteAction(self, syncObj, actionType='move'):
        if actionType== 'remove':
            self.RemoveAction(syncObj)
        elif actionType == 'move':
            self.MoveAction(syncObj)
        elif actionType == "create":
            self.CreateAction(syncObj)
        else:
            msg = "Received unknown Action".format(actionType)
            logging.error(msg)
            raise TypeError(msg)

    def ExecuteSync(self, toRemove: list[SyncTask], toCreate: list[SyncTask], toMove: list[SyncTask] ):
        if toRemove or toCreate or toMove:
            logging.warning("Attempting Sync Execution")
            if toRemove:
                logging.warning("Removing unnecessary Files")
                for syncObj in toRemove:
                    self.ExecuteAction(syncObj=syncObj,actionType='remove')

            if toCreate:
                logging.info("Creating new Folders")
                for syncObj in toCreate:
                    self.ExecuteAction(syncObj=syncObj,actionType='create')

            if toMove:
                logging.info("Synchronizing new Files")
                for syncObj in toMove:
                    logging.info("Synchronizing File {}".format(syncObj.mirrorPath))
                    self.ExecuteAction(syncObj=syncObj,actionType='move')
        else:
            logging.info("Nothing to be done, Skipping Syncing.")

        logging.info("Execution of Syncing Has been Finished Successfully.")