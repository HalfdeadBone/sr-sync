import sys
import logging
from paramiko import ssh_exception
from lib.dataformats import HashDict

class OsSSHOperations():
    def __init__(self, client):
        self.platform = None
        self.client = client
        self.platformCommands = {"MacOS":'sw_vers', "Linux": 'uname', "Win":'ver'}
        self.md5 = {"Linux": "md5sum -b", "Win": "", "MacOS": "md5"}

    def _decodeSSHCommandOutput(self,output):
        return output.read().decode('ascii').strip("\n")

    def GetPlatform(self):
        for t, cmd in self.platformCommands.items():
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd)
                err = self._decodeSSHCommandOutput(stderr)
                if err:
                    logging.info("Not {} platform".format(t))
                else: self.platform = t
            except Exception as e:
                logging.error(e)
                raise(e)
        if not self.platform:
            msg = "Could not find platform for the config. Couldn't execute command"
            logging.error(msg)
            raise(Exception(msg))
        return(self.platform)

    def _MD5ToJSON(self, raw, relPath):
        out = []
        lines = raw.split("\n")
        for line in lines:
            md5, path = line.split(" *")
            path = path.removeprefix(relPath)
            out.append(HashDict(md5, path))
        return out
        

    def HashOut(self, path, relPath, raw=False):
        if type(path) == list:
            path = " ".join(str(x) for x in path)
        try: 
            cmd = self.md5[self.platform] + " " + path
            stdin, stdout, stderr = self.client.exec_command(cmd)
            out = self._decodeSSHCommandOutput(stdout)
        except Exception as e:
            logging.error(e)
            raise(e)
        if not raw:
            out = self._MD5ToJSON(out, relPath)
        return out

        # nie sprawdzaj bulka -> nie ma sensu utrudniasz sobie. 
        # szybciej? Tak, Komplikacje przy linkowaniu statów?, Tak
        