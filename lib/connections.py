import paramiko
from datetime import datetime
import os
import json
import stat
import logging
import hashlib
import lib.dataformats as dataformats
from lib.dataformats import PathDict, HashDict, SyncTask
from lib.os import OsSSHOperations

paramiko.util.log_to_file("paramiko.log")


class SimpleSSHClient:
    def __init__(self, config=None, user=None, hostname=None):
        self.session = paramiko.SSHClient()
        self.sftp = None
        self.name = None
        self.hostname = hostname
        self.user = user
        self.pwd = ""
        self.config = config
        self._SetConfigValues()

    def _SetConfigValues(self):
        if self.config:
            self.hostname = self.config.hostname
            self.user = self.config.user
            self.key = self.config.keyPath if self.config.keyPath else None
            self.pwd = self.config.pwd

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

    def _ValidationMirrorTargetPath(self, syncObj, name):
        filename = syncObj.GetRemotePath().split("/")[-1]
        if not syncObj.GetLocalPath().split("/")[-1] == filename:
            msg = "Config wrongly configured - matched Directory and File, for {} in 'paths': {}".format(
                name, syncObj.__dict__
            )
            logging.error(msg)
            raise (TypeError(msg))

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

    def _GetListSyncPathRemoteFiles(self, syncObj, originalPath=None):
        remoteList = []
        ## Should be in ConfigLoader :/
        self._ValidationMirrorTargetPath(syncObj=syncObj, name=self.name)
        syncObj = self._StatSyncPathRemote(syncObj)
        if syncObj:
            if syncObj.isDir:
                remoteList.extend(self._GetSyncPathRemoteFolder(syncObj=syncObj))
            else:
                remoteList.append(syncObj)
        return remoteList

    def _CombineMirrorAndTarget(
        self, foundPath, fillPath, remoteMirror, originalRemoteFolder, isDir
    ):
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

    def _GetTargetStat(self, path):
        targetStat = None
        try:
            targetStat = self.sftp.stat(path)
        except Exception as e:
            logging.error("Target Doesnt Exist: {}".format(path))
            logging.error(e)
        return targetStat

    def EstablishSftp(self):
        self._ConnectToHost()
        self.sftp = self.session.open_sftp()

    def _GetLocalPathDict(self, pathList, originalPath=None):
        pass

    def ReSyncListOfSyncTask(self, syncTaskList):
        a = self.config.GetPathList()
        fresh = [data for data in self._GetListSyncPathRemoteFiles(a[0])]

        oldSync = set([json.dumps(x.__dict__) for x in syncTaskList])
        newSync = set([json.dumps(x.__dict__) for x in fresh])
        toDownload = None
        toRemove = None

        if not oldSync == newSync:
            toDownload = oldSync & newSync
            toRemove = oldSync - newSync
            toDownload = [SyncTask(**json.loads(x)) for x in toDownload]
            toRemove = [SyncTask(**json.loads(x)) for x in toRemove]

        newSync = [SyncTask(**json.loads(x)) for x in newSync]
        return toDownload, toRemove, newSync

    def GetPathDict(
        self, pathList, originalPath="", remote=True, ignoreDir=True
    ) -> list:
        """
        Creates list of objects: PathDict, that represents local and remote connection()

        :param pathList     :List of Syncronized objects: SyncTask, represening Task
        :param originalPath :String containing original remote path, before reentering. Set by method
        :param remote       :checks if Mirror is remote (not used for now)
        :param ignoreDir    :Bool representing if Dir should be added to finalList

        :returns: List[PathDict] or empty list
        """
        finalList = []
        for pathObj in pathList:
            if not originalPath:
                originalPath = pathObj.GetRemotePath()
            targetStat = self._GetTargetStat(pathObj.GetRemotePath())
            if targetStat:
                subDir = pathObj.GetSubDirFromRemotePath(originalPath=originalPath)
                if self._IsDir(targetStat.st_mode):
                    subDir = pathObj.GetSubDirFromRemotePath(originalPath=originalPath)
                    if not originalPath == pathObj:
                        finalList.append(
                            PathDict(
                                **pathObj.__dict__,
                                subDir=subDir,
                                filename=None,
                                st_mode=targetStat.st_mode,
                                relPath=subDir,
                            )
                        )
                    # pathList =  self._ListAllRemoteFile(pathObj, returnDir=False)
                    # finalList.extend(self.GetPathDict(pathList = pathList, originalPath=originalPath))
                else:
                    filename = str(pathObj.GetRemotePath().split("/")[-1])
                    subDir = pathObj.GetSubDirFromRemotePath(originalPath=originalPath)
                    finalList.append(
                        PathDict(
                            **pathObj.__dict__,
                            subDir=subDir,
                            filename=filename,
                            st_mode=targetStat.st_mode,
                            st_mtime=targetStat.st_mtime,
                            relPath=subDir + filename,
                        )
                    )
        return finalList

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

    def NewGetRemoteListPathDict(
        self, pathList, originalPath=None, remote=True, ignoreDir=True
    ) -> list:
        """
        Creates list of objects: PathDict, that represents local and remote connection()

        :param pathList     :List of Syncronized objects: SyncTask, represening Task
        :param originalPath :String containing original remote path, before reentering. Set by method
        :param remote       :checks if Mirror is remote (not used for now)
        :param ignoreDir    :Bool representing if Dir should be added to finalList

        :returns: List[PathDict] or empty list
        """

        finalList = []
        for pathObj in pathList:
            if ignoreDir and pathObj.isDir:
                continue
            else:
                pathDict = self._GetRemotePathDict(
                    syncObj=pathObj, originalPath=originalPath, ignoreDir=ignoreDir
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
        targetStat = self._GetTargetStat(syncObj.GetRemotePath())
        if targetStat:
            if self._IsDir(targetStat.st_mode) and ignoreDir:
                return None
            else:
                filename = syncObj.GenerateFilename() if not syncObj.isDir else None
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

    def _RemoteSSHHash(self, pathList, relPath):
        ssh = OsSSHOperations(self.session)
        ssh.GetPlatform()
        return ssh.HashOut(path=pathList, relPath=relPath)

    def GetHash(self, relPath, pathList, remote=True):
        if remote:
            return self._RemoteSSHHash(pathList=pathList, relPath=relPath)
        else:
            return self._LocalHash(pathList=pathList, relPath=relPath)

    def GetChosenTarget(self, filePaths):
        for pathObj in filePaths:
            if not pathObj.filename and not os.path.exists(pathObj.GetLocalPath()):
                os.mkdir(pathObj.GetLocalPath())
                logging.info("Created Directory at {}".format(pathObj.GetLocalPath()))
            if pathObj.filename:
                self.sftp.get(
                    localpath=pathObj.GetLocalPath(), remotepath=pathObj.GetRemotePath()
                )

    def OpenTarget(self, path, mode="r", bufsize=-1):
        target = None
        try:
            target = self.sftp.file(filename=path, mode=mode, bufsize=bufsize)
        except IOError as e:
            print(e)
        return target

    def CheckSum(self, a, b) -> bool:
        return self._HashMd5(a) == self._HashMd5(b)

    def RemoveChosenTarget(self, removeList):
        for pathObj in removeList:
            pass

    def PutChosenTarget(self, mirrorPath, targetPath):
        pass

    def UpdatePathsWithHash(self):
        pass

    def ExecuteSync(self, toRemove, toDownload):
        pass
