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
        self.cleanTransfer = self.config.cleanTransfer
        #After Basic Values
        self._SetConfigValues()
        self._ConnectToHost() #Set client
        
        # Init Remote Managment
        self.RemoteManagment = RemoteFilesAndDirs(client = self.session, sftp=self.sftp)

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

    def _LocalHash(self, pathList, relPath) -> list:
        # zrób dla jednego
        hashList = []
        for path in pathList:
            with open(path, "r") as f:
                h = self._HashMd5(f.read())
                hashList.append(HashDict(hash=h, relPath=path.removeprefix(relPath)))
        return hashList

    def ActionMd5Hash(self, syncList):
        toUpdate = []
        for syncObj in syncList:
            if not syncObj.isDir:
                remote = self.RemoteManagment.GetHashMd5(syncObj)
                local = self.LocalManagment.GetHashMd5(syncObj)
                if not local == remote:
                    toUpdate.append(syncObj)
        return toUpdate

    def ActionCheckChanges(self, syncList, hashtype="md5") -> list:
        logging.info("Checking hashes for: {}".format(syncList))
        if hashtype == "md5":
            toUpdate = self.ActionMd5Hash(syncList)
            return toUpdate
        else:
            msg = "Incorrect type of hashing for version control"
            logging.error(msg)
            raise TypeError(msg)

    def OpenTarget(self, path, mode="r", bufsize=-1):
        target = None
        try:
            target = self.sftp.file(filename=path, mode=mode, bufsize=bufsize)
        except IOError as e:
            logging.info(e)
        return target

    
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
            else: syncList.extend(self.LocalManagment.CreateSyncTaskList(taskObj))
        return syncList

    # TODO: IDEA Repetition
    """
    During SyncTask list create 2 lists being Folder and Files, should help with few problems and looping
    for folders and filtering it. I feel like i have 20 isDir questions
    Although More RAM usage :/ But less looping and less checks = less time
    As for hashing... There is a problem how i want to check it
    Considering we've got few scenarios that are not ideal.
    Create Hashmap? Create SyncObj Extended? I cannot (for now and multi os) get sum folder due to 
    Inconsistency between os (for now like i can do custom script but not sure)
    But at the same time looping each time... If loops where spins, i would be the helicopter.
    
    Idea HashMap -> fullPath? Or hash as key for SyncObj, To compare just set(keys)? 
    but still i would need to compare Dirs differently, by tranforming them all into set 
    
    Also -> If multiple sync from different places (in config multiple paths) i could combine it
    But .. idk how hashes would behave. In theory should be fine, especially with sum, but idk
    
    Also Excluding files not to copy... AAAAAAAAAAAAAAAAaaa....
    Handling Delete? Should i delete files in dir???
    
    My comments be like https://www.youtube.com/watch?v=g6t8g6ka4W0
    """
    def ReSyncListOfSyncTask(self, syncTaskList, originalSyncTask: SyncTask):
        # TODO
        # Fix repetition and looping. Hash can be moved to be kept or downloaded to syncTask or do it as a sum
        # Don't synchronize "Files" being dicts

        isClean = self.cleanTransfer

        if originalSyncTask.remoteMirror:
            fresh = [data for data in self.LocalManagment.CreateSyncTaskList(originalSyncTask)]
        else:
            fresh = [data for data in self.RemoteManagment.CreateSyncTask(originalSyncTask)]

        oldSync = set([json.dumps(x.toDict()) for x in copy(syncTaskList) if x])
        newSync = set([json.dumps(x.toDict()) for x in copy(fresh) if x])

        toMove = []
        toRemove = []
        toCreate = []

        if isClean:
            toRemove = newSync - oldSync
            toMove = newSync

            toRemove = [SyncTask(**json.loads(x)) for x in toRemove]
            toCreate = [x for x in toMove if x.isDir]

        else:
            #toRemove = newSync - oldSync
            toMove = newSync if isClean else oldSync - newSync

            #toRemove = [SyncTask(**json.loads(x)) for x in toRemove]
            toMove = [SyncTask(**json.loads(x)) for x in toMove]
            toCreate = [x for x in toMove if x.isDir]

            toCheck = newSync & oldSync
            toCheck = [SyncTask(**json.loads(x)) for x in toCheck]
            toMove.extend(self.ActionCheckChanges(syncList=toCheck))

        targetSync = fresh
        #newSync needs to be verify via HASH, so here should be method for that
        # it would need to return list of task sync, after pathDicts
        # for now no hashing always download all
        return toMove, toCreate, toRemove, targetSync

    def PutChosenTarget(self, syncObj):
        if syncObj.isDir:
            if not self.RemoteManagment.CheckIfFileExists(syncObj.GetRemotePath()):
                logging.info("Creating Folder {}".format(syncObj.GetRemotePath()))
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
            self.RemoteManagment.RemoveTarget(path=syncObj.GetRemotePath(), isDir=syncObj.isDir)
            
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