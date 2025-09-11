import tkinter as tk
from tkinter import filedialog
from ui import AppUI
import logic


class Controller:
    def __init__(self, root):
        self.root = root
        self.ui = AppUI(root)
        self._bind_callbacks()

        # Application state
        self.identifiers = []
        self.holo_cine_files = []
        self.latest_hd_folders = []
        self.latest_ef_folders = []
        self.hd_batch_input = []
        self.ef_batch_input = []

    def _bind_callbacks(self):
        """Binds UI widget events to controller methods."""
        self.ui.input_file_button.config(command=self.select_input_file)
        self.ui.root_folder_button.config(command=self.select_root_folder)
        self.ui.start_button.config(command=self.start_search)

        # Export buttons
        self.ui.export_holo_cine_button.config(command=self.export_holo_cine_files)
        self.ui.export_hd_button.config(command=self.export_hd_folders)
        self.ui.export_missing_hd_button.config(command=self.export_hd_batch_input)
        self.ui.export_ef_button.config(command=self.export_ef_folders)
        self.ui.export_missing_ef_button.config(command=self.export_ef_batch_input)
        self.ui.export_ef_results_button.config(command=self.export_ef_results)

    def select_input_file(self):
        filepath = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        if filepath:
            self.ui.input_file_path.set(filepath)

    def select_root_folder(self):
        folder_path = filedialog.askdirectory(title="Select Root Folder")
        if folder_path:
            self.ui.root_folder_path.set(folder_path)

    def _log_message(self, log_area, message):
        """Helper to insert a message into a specific log area."""
        log_area.config(state=tk.NORMAL)
        log_area.insert(tk.END, message + "\n")
        log_area.config(state=tk.DISABLED)
        log_area.see(tk.END)

    def _clear_logs_and_state(self):
        """Resets the application state for a new search."""
        for log_area in [
            self.ui.holo_cine_log_area,
            self.ui.hd_log_area,
            self.ui.ef_log_area,
        ]:
            log_area.config(state=tk.NORMAL)
            log_area.delete("1.0", tk.END)
            log_area.config(state=tk.DISABLED)

        self.ui.progress_frame.pack_forget()
        self.ui.status_label.config(text="")

        self.identifiers.clear()
        self.holo_cine_files.clear()
        self.latest_hd_folders.clear()
        self.latest_ef_folders.clear()
        self.hd_batch_input.clear()
        self.ef_batch_input.clear()

        # Disable all export buttons
        for button in [
            self.ui.export_hd_button,
            self.ui.export_holo_cine_button,
            self.ui.export_missing_hd_button,
            self.ui.export_ef_button,
            self.ui.export_missing_ef_button,
            self.ui.export_ef_results_button,
        ]:
            button.config(state=tk.DISABLED)

    def start_search(self):
        self._clear_logs_and_state()
        input_file = self.ui.input_file_path.get()
        root_folder = self.ui.root_folder_path.get()

        if not input_file or not root_folder:
            self.ui.status_label.config(
                text="Please select both an input file and a root folder."
            )
            return

        try:
            with open(input_file, "r") as f:
                self.identifiers = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.ui.status_label.config(text=f"Error reading input file: {e}")
            return

        self._setup_progress_bar(len(self.identifiers))

        # --- Perform searches using the logic module ---
        self.holo_cine_files = logic.find_holo_cine_files(
            self.identifiers,
            root_folder,
            progress_callback=self._update_progress_bar,
            error_callback=lambda msg: self._log_message(
                self.ui.holo_cine_log_area, msg
            ),
        )

        self.latest_hd_folders, self.hd_batch_input = logic.find_latest_hd_folders(
            self.holo_cine_files,
            error_callback=lambda msg: self._log_message(self.ui.hd_log_area, msg),
        )

        if self.latest_hd_folders:
            self.latest_ef_folders, self.ef_batch_input = logic.find_latest_ef_folders(
                self.latest_hd_folders,
                error_callback=lambda msg: self._log_message(self.ui.ef_log_area, msg),
            )

        self._finalize_search_and_update_gui()

    def _finalize_search_and_update_gui(self):
        """Updates the GUI with search results and enables relevant buttons."""
        self.ui.progress_frame.pack_forget()

        status_text = (
            f"Search complete. Found {len(self.holo_cine_files)} file(s), "
            f"{len(self.latest_hd_folders)} HD folder(s) ({len(self.hd_batch_input)} missing), "
            f"{len(self.latest_ef_folders)} EF folder(s) ({len(self.ef_batch_input)} missing)."
        )
        self.ui.status_label.config(text=status_text)

        if self.holo_cine_files:
            self.ui.export_holo_cine_button.config(state=tk.NORMAL)
        if self.latest_hd_folders:
            self.ui.export_hd_button.config(state=tk.NORMAL)
        if self.hd_batch_input:
            self.ui.export_missing_hd_button.config(state=tk.NORMAL)
        if self.latest_ef_folders:
            self.ui.export_ef_button.config(state=tk.NORMAL)
            self.ui.export_ef_results_button.config(state=tk.NORMAL)
        if self.ef_batch_input:
            self.ui.export_missing_ef_button.config(state=tk.NORMAL)

    def _setup_progress_bar(self, max_value):
        self.ui.progress_bar["maximum"] = max_value
        self.ui.progress_bar["value"] = 0
        self.ui.progress_label.config(text="0%")
        self.ui.progress_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 5))
        self.root.update_idletasks()

    def _update_progress_bar(self, value):
        self.ui.progress_bar["value"] = value
        percent = int((value / self.ui.progress_bar["maximum"]) * 100)
        self.ui.progress_label.config(text=f"{percent}%")
        self.root.update_idletasks()

    def _export_list_to_file(self, data_list, title):
        if not data_list:
            return
        export_filepath = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        if export_filepath:
            try:
                with open(export_filepath, "w") as f:
                    for path in data_list:
                        f.write(f"{path}\n")
                self.ui.status_label.config(
                    text=f"Successfully exported {len(data_list)} paths."
                )
            except Exception as e:
                self.ui.status_label.config(text=f"Error during export: {e}")

    # --- Export Methods ---
    def export_holo_cine_files(self):
        self._export_list_to_file(self.holo_cine_files, "Save .holo/.cine Paths As")

    def export_hd_folders(self):
        self._export_list_to_file(
            self.latest_hd_folders, "Save Latest HD Folder Paths As"
        )

    def export_hd_batch_input(self):
        self._export_list_to_file(
            self.hd_batch_input, "Save .holo/.cine files not processed by HD as"
        )

    def export_ef_folders(self):
        self._export_list_to_file(
            self.latest_ef_folders, "Save Latest EF Folder Paths As"
        )

    def export_ef_batch_input(self):
        self._export_list_to_file(self.ef_batch_input, "Save EF Batch Input as")

    def export_ef_results(self):
        if not self.latest_ef_folders:
            self.ui.status_label.config(
                text="No EF folders found to export results from."
            )
            return

        destination_root = filedialog.askdirectory(
            title="Select Destination for EF Results"
        )
        if not destination_root:
            return

        self._setup_progress_bar(len(self.latest_ef_folders))

        copied_count, errors = logic.copy_ef_results(
            self.latest_ef_folders,
            self.identifiers,
            destination_root,
            progress_callback=self._update_progress_bar,
            error_callback=lambda msg: self._log_message(self.ui.ef_log_area, msg),
        )

        self.ui.progress_frame.pack_forget()
        if errors:
            self.ui.status_label.config(
                text=f"Export complete with {len(errors)} errors. Copied {copied_count} files."
            )
        else:
            self.ui.status_label.config(
                text=f"Successfully exported results. Copied {copied_count} files."
            )
            if not logic.open_folder(destination_root):
                self._log_message(
                    self.ui.ef_log_area,
                    "[INFO] Could not open destination folder automatically.",
                )
