 # sr-sync (simple r-sync)
 
## About
Project created for the interview and being fixed as side-project for experience.

## State
- [X] sr-sync Conection
    - [X] Auth
    - [X] Connects
    - [X] Sees files 
    - [X] Can verify stat of Files
    - [X] Timeouts
    - [ ] Multi-hostname for Remote to Remote
    - [X] LocalTarget
        - [X] Download
        - [X] Remove
        - [X] Create
        - [ ] cmdline capabilities
    - [X] RemoteTarget
        - [X] Create
        - [X] Remove
        - [X] Put
        - [X] platform Matching
        - [ ] SSH cmdline capabilities 
    - [ ] Hash Version Control
- [X] Sync (`One2Zero`)
    - [X] One Way 
        - [X] Remote Mirror, Local Target
        - [X] Local Mirror, Remote Target
        - [ ] Remote Mirror, Remote Mirror
    - [ ] Advanced sync (`One2One`) 
        - [ ] Keeps track of changes
- [X] Config Support:
    -[X] `ClientConfig`
    -[ ] `GlobalConfig`
    -[ ]  Substitute missing values from GlobalConfig
- [X] Interactive args
    - [X] `autorun` - to run based on configs in /conf/* (ignoresGLobals)
    - [X] `loadconfig` - loads only chosen config From anywhere
    - [X] `manual` - inline config creation
    - [ ] `overview` - TUI/Cli to show status of current jobs/Configs
        - [ ] name, status, downloads, sync time, changes
        - [ ] config disable, enable
        - [ ] target disable, enable
- [ ] Tests
- [ ] Run Without venv
- [X] Timeouts
- [ ] HashVersion control
- [ ] Clean Code
    - [ ] Repetition
    - [ ] Formating PEP
    - [ ] `class` Clarity and integrity (Names And Location, fe. jobs of putting/sendig/removing -> sshclient, but functions to do those and manage in Remote- and Local- FilesandDirs)
    - [ ] ErrorCodes in File, to keep track of them.
- [ ] Multiprocessing / thread per config (Only when all above done AND CLEAN)
  - [X] Separate Configs
  - [ ] Config valdiation for overlaping
    - [ ] Overhaul of the configs, to account for specific tasks and avoidance of multiple config repetitions or conflicts for same Folder For Multiple hosts.
    - [ ] `ClientConfig` changes name to `JobConfig`, and move `hostname`,`user`, `key`, `pwd`, `passwordReq` `paths` to new `targets: list[TargetSync()]`. Each target happens after another in order. `mirrorRemote` will be default in `TargetSync`, but the one in `paths:[SyncType]` will be dominant 
  - [ ] Scheduler
    
## Notice 
LOCAL MIRROR to REMOTE SOURCE is broken.

## Installation
Download and create `virtualenv` with name `venv` and enter it with `source`
```bash
python -m virtualenv ve- [ ] Clean Code
source  venv/bin/activate
pip3 install -r requierments.txt
```

## Usage

There are 2 style of using the program:
- cmdline
- configs

### Cmd

cmd parameters have 3 subcommands being: `autorun`, `localconfig`, `manual`. 
- `autorun` preluidium to threading, but also autostart, that read all configs created at `sr-sync/conf`
- `loadconfig` is manual start for certain config, might be outside the `sr-sync/conf`. Use `-p` to enter full path
- `manual`  use -h for more info, It takes only one mirror-path and target-path. To use multiple instances use config.
```commandline
pytest main.py manual -N <distinct-name> -H <hostname> -M  <mirror-path> -T <target-path> -u <remote-user> -k  <key-location>  -t <ssh-timeout-in-sec>
```



### ClientConfig
| Name | Explenation | Default|
|:------:|------|:------:|
|`syncType` (string) | `Zero2One`- One way sync where client treats mirror device as absolute version, and all is downloaded to target <br>  `One2One` - versions are tracked and sync in between each other | `Zero2One`|


