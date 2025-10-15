import sys
import datetime
import traceback
import re
import atexit
from pathlib import Path


# TODO: Could add a method to have a global log_file, and then switch to eatch
#       sub_log files

# TODO: Maybe add a way to have a auto filename (I don't like the way it is done
#       currently)


def _strip_ansi_codes(text: str) -> str:
    """Removes ANSI escape sequences from a string."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class Tee:
    """
    A context manager that duplicates stdout and stderr to a specified log file.
    """

    def __init__(self):
        self.file = None
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.original_excepthook = sys.excepthook
        self._atexit_registered = False


    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Custom exception handler to log unhandled exceptions to the file."""
        if self.file:
            traceback_details = "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )
            self.write_to_file_only("\n--- UNHANDLED EXCEPTION ---\n")
            self.write_to_file_only(traceback_details)
            self.write_to_file_only("--- END OF EXCEPTION ---\n\n")
            self.flush()

        # Call the original excepthook to display the error in the console
        self.original_excepthook(exc_type, exc_value, exc_traceback)

    
    def start(self, filename: str | Path, redirect_stderr: bool = True):
        """Starts redirecting output to the given file."""
        if self.file:
            return  # Already started
        
        if not self._atexit_registered:
            atexit.register(self.stop)
            self._atexit_registered = True

        try:
            self.file = open(filename, "a", encoding="utf-8")
            sys.stdout = self
            if redirect_stderr:
                sys.stderr = self
            sys.excepthook = self._handle_exception

            self.write_to_file_only(
                f"\n--- SESSION STARTED AT {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n"
            )
        except Exception as e:
            # If starting fails, restore everything to avoid a broken state
            self.original_stdout.write(f"[ERROR] Failed to start Tee handler: {e}\n")
            self.stop()

    def stop(self):
        """Restores original streams and closes the log file."""
        if not self.file:
            return

        self.flush()
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        sys.excepthook = self.original_excepthook

        if self.file:
            self.file.close()
            self.file = None


    def write(self, data, strip_ansi: bool = False):
        """Writes data to both the original stdout and the log file."""
        self.original_stdout.write(data)
        if self.file:
            try:
                if strip_ansi:
                    clean_data = _strip_ansi_codes(data)
                else:
                    clean_data = data
                self.file.write(clean_data)
                self.flush()
            except (IOError, ValueError):
                self.original_stdout.write(
                    "\n[ERROR] (Tee.write) Could not write to log file.\n"
                )

    def write_to_file_only(self, data: str):
        """Writes data only to the log file."""
        if self.file:
            try:
                self.file.write(data)
                self.flush()
            except (IOError, ValueError):
                self.original_stdout.write(
                    "\n[ERROR] (Tee.write_to_file_only) Could not write to log file.\n"
                )

    def flush(self):
        """Flushes both the original stdout and the log file."""
        self.original_stdout.flush()
        if self.file:
            self.file.flush()

    def log_and_reraise(self):
        # This block catches any exception during the app's execution.
        # Format the full traceback.
        error_details = traceback.format_exc()

        # Write the details to the log file using the Tee handler.
        # This bypasses stdout and writes directly to the file.
        tee_handler.write_to_file_only("\n--- STREAMLIT-HANDLED EXCEPTION ---\n")
        tee_handler.write_to_file_only(error_details)
        tee_handler.write_to_file_only("--- END OF EXCEPTION ---\n\n")

        # Re-raise the exception so Streamlit can catch it and display
        # its default error message in the web UI.
        raise

    def __getattr__(self, attr):
        """
        Makes the Tee object behave like the original stdout for other attributes.
        """
        return getattr(self.original_stdout, attr)
    



# TODO: Should really change that (only a import possible for NOW)
tee_handler = Tee()