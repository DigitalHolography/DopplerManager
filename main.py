import os
from src.Logger.LoggerClass import Logger
from src.FinderTools.FileFinderClasss import FileFinder
from src.Utils.ParamsLoader import ConfigManager

# Logger.debug("Testing the Debug", "FILESYSTEM")

def main():
    ROOT_DIR = "Y:\\"  # Change to the real root
    DB_PATH = "collected_data.db"

    FileFinderInstance = FileFinder(DB_PATH)
    FileFinderInstance.CreateDB()

    Logger.info("Scanning directories...")
    data = FileFinderInstance.Findfiles(ROOT_DIR)

    # print(f"Found {len(data)} HD folders.")
    
    # print("Creating database...")
    # conn = create_database(DB_PATH)

    # print("Storing data...")
    # store_data(conn, data)

    # print("Done.")
    # conn.close()

if __name__ == "__main__":
    # For the colored output on Windows
    if os.name == 'nt':
        os.system('')
        
    main()