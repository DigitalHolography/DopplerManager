import sqlite3
import os
from src.Logger.LoggerClass import Logger
from src.Utils.ParamsLoader import ConfigManager


class DB:
    # TODO: Implem in_memory DB option
    def __init__(
        self,
        DB_PATH: str,
        SQLconnect: sqlite3.Connection | None = None,
        check_same_thread: bool = False,
    ):
        self.DB_PATH = DB_PATH
        self.check_same_thread = check_same_thread

        if SQLconnect:
            self.SQLconnect = SQLconnect
        else:
            if not ConfigManager.get("DB.OVERRIDE_DB") and os.path.exists(str(DB_PATH)):
                Logger.warn(
                    f"Database file already exists at {DB_PATH}. To override it, set DB.OVERRIDE_DB to true in settings.json",
                    "DATABASE",
                )
            else:
                if os.path.exists(str(DB_PATH)):
                    Logger.info(
                        f"Overriding existing database at {DB_PATH}", "DATABASE"
                    )
                    os.remove(str(DB_PATH))

            self.SQLconnect = sqlite3.connect(
                DB_PATH, check_same_thread=check_same_thread
            )

        # Forces the foreign Keys (duh)
        self.SQLconnect.execute("PRAGMA foreign_keys = ON;")
        self.SQLconnect.execute("PRAGMA journal_mode = WAL;")

    def check_table_existance(self, table_name: str) -> bool:
        """Will check if the table exists inside the DB

        Args:
            table_name (str): The name of the table

        Returns:
            bool: True if `table_name` exists, False otherwise
        """

        if not table_name.isidentifier:
            Logger.error(
                f"Table name is not a valid identifier ({table_name})", "DATABASE"
            )
            return False

        res = self.SQLconnect.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """,
            (table_name,),
        )
        return res.fetchone() is not None

    def create_table(self, table_name: str, columns: dict[str, str]) -> None:
        """Create a SQLite table

        Args:
            table_name (str): The name of the table
            columns (dict[str, str]): The columns of the table
        """

        # Maybe store the tables for easy recreation

        # Security check
        if not table_name.isidentifier:
            Logger.fatal(
                f"Table name is not a valid identifier ({table_name})", "DATABASE"
            )
            return

        if self.check_table_existance(table_name):
            Logger.warn(f"{table_name} already exists", "DATABASE")
            return

        for name, _ in columns.items():  # Is not checking for SQLInjection in type
            if not name.isidentifier:
                Logger.fatal(
                    f"Table column name is not a valid identifier ({name})", "DATABASE"
                )
                return

        cols = ", ".join([f"{name} {type}" for name, type in columns.items()])
        SQL_COMMAND = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols})"

        self.SQLconnect.execute(SQL_COMMAND)
        self.SQLconnect.commit()

    def insert(
        self, table_name: str, data: dict[str, object], do_commit: bool = True
    ) -> int | None:
        """Inserts `data` inside the `table_name`

        Args:
            table_name (str): The name of the table
            data (dict[str, str]): The data to be added
        """
        if not table_name.isidentifier:
            Logger.fatal(
                f"Table name is not a valid identifier ({table_name})", "DATABASE"
            )
            return

        if not self.check_table_existance(table_name):
            Logger.error(f"{table_name} does not exists", "DATABASE")
            return

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        SQL_COMMAND = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        cursor = self.SQLconnect.execute(SQL_COMMAND, tuple(data.values()))

        if do_commit:
            self.SQLconnect.commit()

        return cursor.lastrowid

    def select(
        self, table_name: str, condition: dict[str, object] | None = None
    ) -> list[dict]:
        """Searchs the DB with given parameters

        Args:
            table_name (str): The name of the table
            condition (dict[str, object] | None, optional): The conditions of search. Defaults to None.

        Returns:
            list[dict]: A list of found matching entries
        """

        if not self.check_table_existance(table_name):
            Logger.error(f"{table_name} does not exists", "DATABASE")
            return []

        if condition:
            conds = " AND ".join([f"{k} = ?" for k in condition.keys()])
            sql = f"SELECT * FROM {table_name} WHERE {conds}"
            cursor = self.SQLconnect.execute(sql, tuple(condition.values()))
        else:
            sql = f"SELECT * FROM {table_name}"
            cursor = self.SQLconnect.execute(sql)

        return [dict(row) for row in cursor.fetchall()]

    # def close(self):
    #     self.SQLconnect.close()

    def clear_db(self) -> None:
        self.SQLconnect.close()

        try:
            if os.path.exists(self.DB_PATH):
                os.remove(self.DB_PATH)
            else:
                Logger.error(f"Error removing database file {self.DB_PATH}", "DATABASE")
        except OSError as e:
            Logger.error(
                f"Error removing database file {self.DB_PATH}: {e}", "DATABASE"
            )

        self.SQLconnect = sqlite3.connect(
            self.DB_PATH, check_same_thread=self.check_same_thread
        )

        Logger.info(f"Successfully cleared DB: {self.DB_PATH}", "DATABASE")

    def upsert(self, table_name: str, data: dict[str, object]) -> int | None:
        """
        Inserts data into the table. If a row with the same primary key already exists,
        it replaces the existing row (INSERT OR REPLACE).
        """
        if not table_name.isidentifier():
            Logger.fatal(
                f"Table name is not a valid identifier ({table_name})", "DATABASE"
            )
            return

        if not self.check_table_existance(table_name):
            Logger.error(f"{table_name} does not exist", "DATABASE")
            return

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        SQL_COMMAND = (
            f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
        )

        cursor = self.SQLconnect.execute(SQL_COMMAND, tuple(data.values()))
        self.SQLconnect.commit()

        return cursor.lastrowid

    def count(self, table_name: str) -> int:
        """Counts the number of rows in a table.

        Args:
            table_name (str): The name of the table.

        Returns:
            int: The number of rows in the table.
        """
        if not self.check_table_existance(table_name):
            Logger.error(f"{table_name} does not exist", "DATABASE")
            return 0

        cursor = self.SQLconnect.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()

        return count[0] if count else 0
