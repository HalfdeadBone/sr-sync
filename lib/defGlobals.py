from dotenv import load_dotenv
import os

load_dotenv()

virutalEnvLoc = os.environ['VIRTUAL_ENV'] 
appFolder = virutalEnvLoc + "/../"
configFolder = appFolder + os.environ['CONFIG_FOLDER']
keysFolder = appFolder + os.environ['KEYS_FOLDER']
globalConfig = configFolder + "global.json"