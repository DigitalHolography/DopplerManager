import tkinter as tk
from tkinter import scrolledtext, ttk

class AppUI:
    def __init__(self, root):
        root.title("Doppler Batch Input Tool")
        root.geometry("850x700")

        self.input_file_path = tk.StringVar()
        self.root_folder_path = tk.StringVar()

        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._setup_selection_frame(main_frame)
        self.start_button = tk.Button(main_frame, text="Start Search")
        self.start_button.pack(pady=(10,5), ipady=5, fill=tk.X)

        self._setup_export_frames(main_frame)
        self._setup_log_notebook(main_frame)
        self._setup_bottom_frame(main_frame)

    def _setup_selection_frame(self, parent):
        selection_frame = tk.Frame(parent)
        selection_frame.pack(fill=tk.X)
        selection_frame.columnconfigure(1, weight=1)

        self.input_file_button = tk.Button(selection_frame, text="Select Input File")
        self.input_file_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        input_file_label = tk.Label(selection_frame, textvariable=self.input_file_path, relief="sunken", anchor="w", padx=5)
        input_file_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.root_folder_button = tk.Button(selection_frame, text="Select Root Folder")
        self.root_folder_button.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="ew")
        root_folder_label = tk.Label(selection_frame, textvariable=self.root_folder_path, relief="sunken", anchor="w", padx=5)
        root_folder_label.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    def _setup_export_frames(self, parent):
        export_found_frame = tk.LabelFrame(parent, text="Export Found Items", padx=5, pady=5)
        export_found_frame.pack(fill=tk.X, pady=5)
        for i in range(2): export_found_frame.columnconfigure(i, weight=1)

        self.export_holo_cine_button = tk.Button(export_found_frame, text="Export .holo/.cine paths", state=tk.DISABLED)
        self.export_holo_cine_button.grid(row=0, column=0, padx=(0, 5), pady=5, ipady=5, sticky="ew")

        self.export_hd_button = tk.Button(export_found_frame, text="Export latest HD folder paths", state=tk.DISABLED)
        self.export_hd_button.grid(row=0, column=1, padx=(5, 0), pady=5, ipady=5, sticky="ew")

        self.export_ef_button = tk.Button(export_found_frame, text="Export latest EF folder paths", state=tk.DISABLED)
        self.export_ef_button.grid(row=1, column=0, padx=(0, 5), pady=5, ipady=5, sticky="ew")

        self.export_ef_results_button = tk.Button(export_found_frame, text="Export EF results", state=tk.DISABLED)
        self.export_ef_results_button.grid(row=1, column=1, padx=(5, 0), pady=5, ipady=5, sticky="ew")

        export_missing_frame = tk.LabelFrame(parent, text="Export Batch Inputs", padx=5, pady=5)
        export_missing_frame.pack(fill=tk.X, pady=5)
        for i in range(2): export_missing_frame.columnconfigure(i, weight=1)

        self.export_missing_hd_button = tk.Button(export_missing_frame, text="Export HoloDoppler Batch Input", state=tk.DISABLED)
        self.export_missing_hd_button.grid(row=0, column=0, padx=(0, 5), ipady=5, sticky="ew")

        self.export_missing_ef_button = tk.Button(export_missing_frame, text="Export EyeFlow Batch Input", state=tk.DISABLED)
        self.export_missing_ef_button.grid(row=0, column=1, padx=(5, 0), ipady=5, sticky="ew")

    def _setup_log_notebook(self, parent):
        log_notebook = ttk.Notebook(parent)
        log_notebook.pack(pady=5, fill=tk.BOTH, expand=True)

        self.holo_cine_log_area = self._create_log_tab(log_notebook, ".holo/.cine Logs")
        self.hd_log_area = self._create_log_tab(log_notebook, "HD Folder Logs")
        self.ef_log_area = self._create_log_tab(log_notebook, "EF Folder Logs")

    def _create_log_tab(self, notebook, text):
        tab = tk.Frame(notebook)
        notebook.add(tab, text=text)
        log_area = scrolledtext.ScrolledText(tab, wrap=tk.WORD, height=10, state=tk.DISABLED)
        log_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        return log_area

    def _setup_bottom_frame(self, parent):
        bottom_frame = tk.Frame(parent)
        bottom_frame.pack(side=tk.BOTTOM, pady=(5, 0), fill=tk.X)

        self.progress_frame = tk.Frame(bottom_frame)
        self.progress_frame.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient='horizontal', mode='determinate')
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_label = tk.Label(self.progress_frame, text="0%")
        self.progress_label.grid(row=0, column=1, padx=(5,0))

        self.status_label = tk.Label(bottom_frame, text="Please select your input file and root folder.", relief="sunken", anchor="w", padx=5)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)