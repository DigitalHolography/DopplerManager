import sys
import datetime
from pathlib import Path

# TODO: Could add a method to have a global log_file, and then switch to eatch
#       sub_log files

# TODO: Maybe add a way to have a auto filename (I don't like the way it is done
#       currently)


class Tee:
    """
    A context manager that duplicates stdout and stderr to a specified log file.
    """

    def __init__(
        self,
        filename: str | Path,
        open_mode: str = "a",
        file_encoding: str = "utf-8",
    ):
        self.filename = filename
        self.open_mode = open_mode
        self.file_encoding = file_encoding

        self.file = None
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def __enter__(self):
        """
        Activates the redirection when entering the 'with' block.
        """
        self.file = open(self.filename, self.open_mode, encoding=self.file_encoding)

        sys.stdout = self
        sys.stderr = self

        self.write(
            f"\n--- SESSION STARTED AT {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n"
        )

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Restores original streams and closes the file when exiting the 'with' block.
        This method is called automatically, even if errors occur.
        """
        self.flush()

        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

        if self.file:
            self.file.close()
            self.file = None

    def write(self, data):
        """
        Writes data to both the original stdout and the log file.
        """

        if not self.file:
            self.original_stdout.write(
                "\n[ERROR] (write) Log file is not initialized\n"
            )
            self.original_stdout.write(data)
            return

        try:
            self.original_stdout.write(data)
            self.file.write(data)
        except (IOError, ValueError):
            # If logging fails, fall back to writing only to the original stdout
            self.original_stdout.write(
                "\n[ERROR] (write) Could not write to log file.\n"
            )
            self.original_stdout.write(data)

    def flush(self):
        """
        Flushes both the original stdout and the log file.
        """
        if not self.file:
            self.original_stdout.write(
                "\n[ERROR] (flush) Log file is not initialized\n"
            )
            self.original_stdout.flush()
            return

        self.original_stdout.flush()
        self.file.flush()

    def __getattr__(self, attr):
        """
        Makes the Tee object behave like the original stdout for other attributes.
        """
        return getattr(self.original_stdout, attr)
