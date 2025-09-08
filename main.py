import os
from src.Logger.LoggerClass import Logger
from src.FinderTools.FileFinderClasss import FileFinder
from src.Utils.ParamsLoader import ConfigManager

# Logger.debug("Testing the Debug", "FILESYSTEM")

def main():
    ROOT_DIR = ConfigManager.get("FINDER.DEFAULT_ROOT_DIR")  # "Y:\\"  # Change to the real root
    DB_PATH = ConfigManager.get("DB.DB_PATH")

    if not ROOT_DIR:
        Logger.error("FINDER.DEFAULT_ROOT_DIR is not set in the configuration.", "FILESYSTEM")
        return
    
    if not DB_PATH:
        Logger.error("DB.DB_PATH is not set in the configuration.", "FILESYSTEM")
        return

    if not ConfigManager.get("DB.OVERRIDE_DB") and os.path.exists(DB_PATH):
        Logger.warn(f"Database file already exists at {DB_PATH}. To override it, set DB.OVERRIDE_DB to true in settings.json", "DATABASE")
    else:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

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
    
# def test():
#     print(json.dumps(ConfigManager.get_all_settings(), indent=4))
#     print(ConfigManager.get("DB.DB_PATH"))
#     ConfigManager.set("DB.TRUC.TEST", "lol")
#     print(json.dumps(ConfigManager.get_all_settings(), indent=4))

if __name__ == "__main__":
    # For the colored output on Windows
    if os.name == 'nt':
        os.system('')
        
    main()