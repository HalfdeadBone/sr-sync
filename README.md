# sr-sync (simple r-sync)
## State
- [X] sr-sync Conection
    - [X] Auth
    - [X] Connects
    - [X] Sees files 
    - [X] Can verify stat of Files
    - [ ] Multi-hostname for Remote to Remote
    - [ ] Local
        - [X] Put
        - [X] Remove
        - [X] Create
        - [ ] SSH Functions to use
    - [ ] Remote
        - [X] Download
        - [ ] Create
        - [ ] Remove
        - [ ] Put
        - [ ] SSH Functions to use 
- [X] Sync (`One2Zero`)
    - [X] One Way 
        - [X] Remote Mirror, Local Target
        - [ ] Local Mirror, Remote Target
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
- [ ] Tests
- [ ] Run Without venv
- [ ] Timeouts
- [ ] Multiprocessing / thread per config
    - [X] Separate Configs
    - [ ] scheduler
    - [ ] Config valdiation for overlaping
 
## Installation

## Global Config
| Name | Explenation | Default|
|:------:|------|:------:|
|`syncType` (string) | `Zero2One`- One way sync where client treats mirror device as absolute version, and all is downloaded to target <br>  `One2One` - versions are tracked and sync in between each other | `Zero2One`|
|`time` (json) | Keeps parameters like `timeInterval` and `timeOveride` | |
|`excludeSyncName` (arr[string]) | Excludes configs with given name of the file | `[]`|
||

