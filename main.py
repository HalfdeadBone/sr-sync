import os
import paramiko
import lib.files as files
from lib.cmd import *
import lib.connections as connections
from lib.dataformats import *

import hashlib
import json
import sys
    
def main():
    # Check Structure
    localOp = files.ConfigLoader()
    if localOp.CheckIfConfigFolderExists():
        localOp.AddMissingFolders()

    # Load Argvs and init coresponding
    cfg = None
    par = InitInlineParser()
    command = str(set(sys.argv)&{"loadconfig","autorun", "manual"})
    if command == "manual":
        cfg = localOp.GenerateClientConfig(
            name=par.job_name, 
            hostname=par.hostname,
            user=par.user,
            isDir=par.is_dir,
            mirrorPath=par.mirrorPath,
            targetPath=par.targetPath,
            keyPath=par.key,
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


if __name__ == "__main__":
    main()