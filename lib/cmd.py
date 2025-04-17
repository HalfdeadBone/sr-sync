import argparse
import lib.dataformats as dataformats

def InitInlineParser():
    parser = argparse.ArgumentParser(
        prog = 'sr-sync (simple r-sync)',
        description = 
            '''
            Recursive Simple SSH allows for OneWay sync via sftp and SSH (in case of Hashing)
            It can be used via terminal in a simplified way or via configs (.json) to set
            neccesery data for it's connection. 
            ''',
        epilog = "Use with cautiousness",
        add_help = True
    )
    subparser = parser.add_subparsers()    

    ### AutoSync -> Starts whole main Sequence
    autoSync = subparser.add_parser('autorun', help='')

    configSync = subparser.add_parser("loadconfig", help= "Takes string indentyfing filename of the config") 
    configSync.add_argument("-P", "--path", help= "Takes string indentyfing filename of the config", type=str)

    inlineSync = subparser.add_parser('manual', help='GetValue')
    inlineSync.add_argument("-H", "--hostname", help="{Req) Takes string, representing targetHostname", type=str)
    inlineSync.add_argument("-u", "--user", help="(Req) Takes str being representative of username for remote instance", type=str)
    inlineSync.add_argument("-M","--mirrorPath", help="(Req) Takes str being representative of a mirror path of file or dict", type=str)
    inlineSync.add_argument("-T", "--targetPath", help="(Req) Takes str being representative of a target path of file or dict", type=str)
    inlineSync.add_argument("-R", "--remoteMirror", help="{Req) Takes bool representing if the mirrorPath is remote", type=bool,
                            default=True)
    inlineSync.add_argument("-N", "--job_name",
                            help="(Optional) Takes string indentyfing name during download. Random hash if not specified",
                            type=str, default=None)
    inlineSync.add_argument("-d", "--is_dir", help="(Optional) Takes bool representing is path a directory. Both mirror and target should match", type=bool, default=False)
    inlineSync.add_argument("-k", "--key", help="(Optional) Takes string representing path to a key.", type=str, default=None)
    inlineSync.add_argument("-t", "--timeout", help="{Optional) Takes int representing timeout in seconds", type=int, default=120)
    inlineSync.add_argument("-c", "--createConfig", help="{Optional) Takes bool deciding to create a file", type=str, default=False)

    args = parser.parse_args()

    return(args)