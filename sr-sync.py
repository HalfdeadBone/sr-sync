import os
import paramiko
import lib.files as files
from lib.cmd import *
import lib.connections as connections
import  logging

import sys
    
def main():
    logging.getLogger("paramiko").setLevel(logging.CRITICAL)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
        datefmt='%H:%M:%S'
    )
    # Check Structure
    localOp = files.ConfigLoader()
    if localOp.CheckIfConfigFolderExists():
        localOp.AddMissingFolders()

    # Load Argvs and init coresponding
    cfg = None
    par = InitInlineParser()
    command = list(set(sys.argv)&{"loadconfig","autorun", "manual"})[0]
    if command == "manual":
        cfg = localOp.GenerateClientConfig(
            name=par.job_name,
            hostname=par.hostname,
            user=par.user,
            isDir=par.is_dir,
            mirrorPath=par.mirrorPath,
            targetPath=par.targetPath,
            keyPath=par.key,
            timeout=par.timeout,
            remoteMirror=par.remoteMirror,
            toFile= par.createConfig
        )
    elif command =="loadconfig":
        cfg = [localOp.LoadClientConfig(par.path)]
    elif command == "autorun": 
        cfg = localOp.LoadAllClientConfigs()

    ### If Multiprocessing for multiple configs:
    # - Add Scheduler
    # - schedule not by time form start to start, but end to start and only after finishing task or timeout
    # - Rest is ready
    if cfg:
        for config in cfg:
            client = connections.SimpleSSHClient(config)
            # split for now. Could be at the same time, but that would be a problem in the future
            for syncTask in client.config.paths:
                syncList = client.GetSyncTaskList([syncTask])
                toMove, toCreate, toRemove, targetSync = client.ReSyncListOfSyncTask(syncList, originalSyncTask = syncTask)

                # Delete Unnecesery, Then create missing dirs, Then rest.
                client.ExecuteSync(toRemove=toRemove, toCreate=toCreate, toMove=toMove)

if __name__ == "__main__":
    main()