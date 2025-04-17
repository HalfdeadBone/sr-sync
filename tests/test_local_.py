import pytest
from lib.files import *


## class into param
@pytest.fixture
def client_config_valid_data():
    return {
        "configName":"test_data", 
        "hostname":"192.168.0.2",
        "passwordReq":"test",
        "isDir":False,
        "configName": "",
        "configPath":"",
        "keyPath":"/hone/test/.ssh/authkey",
        "pwd": "test",
        "paths": {
            "remoteMirror": "False", 
            "mirrorPath":"/home/test/path", 
            "targetPath":"/home/test/pather",
            "isDir": False}
    }

@pytest.fixture
def client_config_to_file():
    pass 
@pytest.mark.skip
def test_01_load_config():
    pass
@pytest.mark.skip
def test_02_load_config_from_file():
    pass
@pytest.mark.skip
def test_03_create_folder():
    pass

# Remove 04 and 05 could be one test(parametrize)
@pytest.mark.skip
def test_04_remove_folder():
    pass
@pytest.mark.skip
def test_05_remove_nested_folder():
    pass