import FinderUtils
import sqlite3

class FileFinder:
    def __init__(self, DB_PATH):
        # Folder that will be searched
        self.searchFolder = ""
        self.DB_PATH = DB_PATH
        self.SQLconnect = sqlite3.connect(DB_PATH)

    def CreateDB(self):
        cursor = self.SQLconnect.cursor()