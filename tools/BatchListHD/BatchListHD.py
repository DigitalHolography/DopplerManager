import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import os
import re

# --- Global lists to store the search results ---
holo_cine_files = []
latest_hd_folders = []
latest_ef_folders = []
hd_batch_input = []
ef_batch_input = []

def select_input_file():
    """Opens a file dialog to select the input .txt file."""
    filepath = filedialog.askopenfilename(
        title="Select Input File",
        filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
    )
    if filepath:
        input_file_path.set(filepath)

def select_root_folder():
    """Opens a dialog to select the root folder for the search."""
    folder_path = filedialog.askdirectory(title="Select Root Folder")
    if folder_path:
        root_folder_path.set(folder_path)

def log_holo_cine(message):
    """Inserts a message into the .holo/.cine log area."""
    holo_cine_log_area.config(state=tk.NORMAL)
    holo_cine_log_area.insert(tk.END, message + "\n")
    holo_cine_log_area.config(state=tk.DISABLED)
    holo_cine_log_area.see(tk.END)

def log_hd(message):
    """Inserts a message into the HD folder log area."""
    hd_log_area.config(state=tk.NORMAL)
    hd_log_area.insert(tk.END, message + "\n")
    hd_log_area.config(state=tk.DISABLED)
    hd_log_area.see(tk.END)

def log_ef(message):
    """Inserts a message into the EF folder log area."""
    ef_log_area.config(state=tk.NORMAL)
    ef_log_area.insert(tk.END, message + "\n")
    ef_log_area.config(state=tk.DISABLED)
    ef_log_area.see(tk.END)

def start_search():
    """
    Main function to parse, search for files, find the latest HD and EF folders,
    and update the GUI state based on the results.
    """
    input_file = input_file_path.get()
    root_folder = root_folder_path.get()

    # --- Reset state for a new search ---
    for log_area in [holo_cine_log_area, hd_log_area, ef_log_area]:
        log_area.config(state=tk.NORMAL)
        log_area.delete('1.0', tk.END)
        log_area.config(state=tk.DISABLED)
    
    status_label.config(text="")
    latest_hd_folders.clear()
    holo_cine_files.clear()
    hd_batch_input.clear()
    latest_ef_folders.clear()
    ef_batch_input.clear()
    
    for button in [export_hd_button, export_holo_cine_button, export_missing_hd_button,
                   export_ef_button, export_missing_ef_button]:
        button.config(state=tk.DISABLED)

    if not input_file or not root_folder:
        status_label.config(text="Please select both an input file and a root folder.")
        return

    try:
        with open(input_file, 'r') as f:
            identifiers = [line.strip() for line in f if line.strip()]

        found_files_master_list = []
        top_level_dirs = [d for d in os.listdir(root_folder) if os.path.isdir(os.path.join(root_folder, d))]

        for identifier in identifiers:
            prefix = identifier.split('_')[0]
            matching_top_dirs = [d for d in top_level_dirs if d.startswith(prefix)]

            if not matching_top_dirs:
                log_holo_cine(f"[ERROR] No directory starting with '{prefix}' found for identifier '{identifier}'.")
                continue

            files_found_for_this_identifier = 0
            for dir_name in matching_top_dirs:
                target_dir_path = os.path.join(root_folder, dir_name)
                for dirpath, _, filenames in os.walk(target_dir_path):
                    for filename in filenames:
                        if filename.startswith(identifier) and (filename.endswith('.holo') or filename.endswith('.cine')):
                            absolute_path = os.path.abspath(os.path.join(dirpath, filename))
                            found_files_master_list.append(absolute_path)
                            files_found_for_this_identifier += 1
                            find_latest_hd_folder(dirpath, filename)
            
            if files_found_for_this_identifier == 0:
                log_holo_cine(f"[ERROR] No '.holo' or '.cine' files for '{identifier}' found in its matching directory/directories.")

        # --- Finalize .holo/.cine and HD results ---
        unique_files = sorted(list(set(found_files_master_list)))
        holo_cine_files.extend(unique_files)
        
        # --- Start EF folder search based on unique HD folders found ---
        unique_hd_folders = sorted(list(set(latest_hd_folders)))
        if unique_hd_folders:
            for hd_folder in unique_hd_folders:
                find_latest_ef_folder(hd_folder)

        # --- Update GUI with all results ---
        status_text = (
            f"Search complete. Found {len(holo_cine_files)} file(s), "
            f"{len(unique_hd_folders)} HD folder(s) ({len(hd_batch_input)} missing), "
            f"{len(latest_ef_folders)} EF folder(s) ({len(ef_batch_input)} missing)."
        )
        status_label.config(text=status_text)

        if holo_cine_files: export_holo_cine_button.config(state=tk.NORMAL)
        if latest_hd_folders: export_hd_button.config(state=tk.NORMAL)
        if hd_batch_input: export_missing_hd_button.config(state=tk.NORMAL)
        if latest_ef_folders: export_ef_button.config(state=tk.NORMAL)
        if ef_batch_input: export_missing_ef_button.config(state=tk.NORMAL)

    except Exception as e:
        status_label.config(text=f"An error occurred: {e}")

def find_latest_hd_folder(directory, source_filename):
    """
    Looks for folders matching the source filename pattern, finds the latest, 
    and logs files that are missing them.
    """
    base_name = os.path.splitext(source_filename)[0]
    hd_pattern = re.compile(f"^{re.escape(base_name)}_HD_(\\d+)$")
    candidate_folders = {}
    
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            match = hd_pattern.match(item)
            if match:
                number = int(match.group(1))
                candidate_folders[number] = os.path.abspath(item_path)
    
    if candidate_folders:
        latest_number = max(candidate_folders.keys())
        latest_folder_path = candidate_folders[latest_number]
        if latest_folder_path not in latest_hd_folders:
            latest_hd_folders.append(latest_folder_path)
    else:
        log_hd(f"[WARNING] For '{source_filename}', no corresponding HD folder was found.")
        hd_batch_input.append(os.path.abspath(os.path.join(directory, source_filename)))

def find_latest_ef_folder(hd_folder_path):
    """
    In a given HD folder, looks for an 'eyeflow' directory and then finds the
    latest EF folder inside it, based on the HD folder's name.
    """
    eyeflow_dir = os.path.join(hd_folder_path, "eyeflow")

    if not os.path.isdir(eyeflow_dir):
        log_ef(f"[WARNING] No 'eyeflow' directory found in: {hd_folder_path}")
        ef_batch_input.append(hd_folder_path)
        return

    # The base name for the EF folder search is the full name of the HD folder.
    hd_folder_name = os.path.basename(hd_folder_path)

    # The pattern is [name_of_hd_folder]_EF_[number]
    ef_pattern = re.compile(f"^{re.escape(hd_folder_name)}_EF_(\\d+)$")
    candidate_folders = {}

    for item in os.listdir(eyeflow_dir):
        item_path = os.path.join(eyeflow_dir, item)
        if os.path.isdir(item_path):
            match = ef_pattern.match(item)
            if match:
                number = int(match.group(1))
                candidate_folders[number] = os.path.abspath(item_path)

    if candidate_folders:
        latest_number = max(candidate_folders.keys())
        latest_folder_path = candidate_folders[latest_number]
        latest_ef_folders.append(latest_folder_path)
    else:
        log_ef(f"[WARNING] 'eyeflow' directory exists but no EF folders found in: {hd_folder_path}")
        ef_batch_input.append(hd_folder_path)

def export_list_to_file(data_list, title, success_message):
    """Generic function to export a list of paths to a .txt file."""
    if not data_list: return
    export_filepath = filedialog.asksaveasfilename(
        title=title, defaultextension=".txt",
        filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
    )
    if export_filepath:
        try:
            with open(export_filepath, 'w') as f:
                for path in sorted(list(set(data_list))):
                    f.write(f"{path}\n")
            status_label.config(text=success_message.format(count=len(set(data_list))))
        except Exception as e:
            status_label.config(text=f"Error during export: {e}")

def export_holo_cine_files():
    """Exports the list of found .holo/.cine files to a text file."""
    export_list_to_file(
        holo_cine_files,
        "Save .holo/.cine Paths As",
        "Successfully exported {count} .holo/.cine paths."
    )

def export_hd_folders():
    """Exports the list of latest HD folders to a text file."""
    export_list_to_file(
        latest_hd_folders,
        "Save Latest HD Folder Paths As",
        "Successfully exported {count} HD folder paths."
    )

def export_hd_batch_input():
    """Exports the list of files missing an HD folder."""
    export_list_to_file(
        hd_batch_input,
        "Save .holo/.cine files not processed by HD as",
        "Successfully exported {count} missing HD file paths."
    )

def export_ef_folders():
    """Exports the list of latest EF folders to a text file."""
    export_list_to_file(
        latest_ef_folders,
        "Save Latest EF Folder Paths As",
        "Successfully exported {count} EF folder paths."
    )

def export_ef_batch_input():
    """Exports the list of HD folders not processed by EF."""
    export_list_to_file(
        ef_batch_input,
        "Save EF Batch Input as",
        "Successfully exported {count} missing EF folder paths."
    )

# --- GUI Setup ---
app = tk.Tk()
app.title("File and Folder Finder")
app.geometry("850x600")

input_file_path = tk.StringVar()
root_folder_path = tk.StringVar()

main_frame = tk.Frame(app, padx=10, pady=10)
main_frame.pack(fill=tk.BOTH, expand=True)

selection_frame = tk.Frame(main_frame)
selection_frame.pack(fill=tk.X)
selection_frame.columnconfigure(1, weight=1)

input_file_button = tk.Button(selection_frame, text="Select Input File", command=select_input_file)
input_file_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
input_file_label = tk.Label(selection_frame, textvariable=input_file_path, relief="sunken", anchor="w", padx=5)
input_file_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

root_folder_button = tk.Button(selection_frame, text="Select Root Folder", command=select_root_folder)
root_folder_button.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="ew")
root_folder_label = tk.Label(selection_frame, textvariable=root_folder_path, relief="sunken", anchor="w", padx=5)
root_folder_label.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

start_button = tk.Button(main_frame, text="Start Search", command=start_search)
start_button.pack(pady=(10,5), ipady=5, fill=tk.X)

# --- Export Frames for better layout ---
export_found_frame = tk.LabelFrame(main_frame, text="Export Found Items", padx=5, pady=5)
export_found_frame.pack(fill=tk.X, pady=5)
for i in range(3): export_found_frame.columnconfigure(i, weight=1)

export_holo_cine_button = tk.Button(export_found_frame, text="Export .holo/.cine files", command=export_holo_cine_files, state=tk.DISABLED)
export_holo_cine_button.grid(row=0, column=0, padx=(0, 5), ipady=5, sticky="ew")

export_hd_button = tk.Button(export_found_frame, text="Export latest HD folders", command=export_hd_folders, state=tk.DISABLED)
export_hd_button.grid(row=0, column=1, padx=(5, 5), ipady=5, sticky="ew")

export_ef_button = tk.Button(export_found_frame, text="Export latest EF folders", command=export_ef_folders, state=tk.DISABLED)
export_ef_button.grid(row=0, column=2, padx=(5, 0), ipady=5, sticky="ew")

export_missing_frame = tk.LabelFrame(main_frame, text="Export Batch Inputs", padx=5, pady=5)
export_missing_frame.pack(fill=tk.X, pady=5)
for i in range(2): export_missing_frame.columnconfigure(i, weight=1)

export_missing_hd_button = tk.Button(export_missing_frame, text="Export HoloDoppler Batch Input", command=export_hd_batch_input, state=tk.DISABLED)
export_missing_hd_button.grid(row=0, column=0, padx=(0, 5), ipady=5, sticky="ew")

export_missing_ef_button = tk.Button(export_missing_frame, text="Export EyeFlow Batch Input", command=export_ef_batch_input, state=tk.DISABLED)
export_missing_ef_button.grid(row=0, column=1, padx=(5, 0), ipady=5, sticky="ew")

log_notebook = ttk.Notebook(main_frame)
log_notebook.pack(pady=5, fill=tk.BOTH, expand=True)

holo_cine_tab = tk.Frame(log_notebook)
log_notebook.add(holo_cine_tab, text=".holo/.cine Logs")
holo_cine_log_area = scrolledtext.ScrolledText(holo_cine_tab, wrap=tk.WORD, height=10, state=tk.DISABLED)
holo_cine_log_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

hd_folder_tab = tk.Frame(log_notebook)
log_notebook.add(hd_folder_tab, text="HD Folder Logs")
hd_log_area = scrolledtext.ScrolledText(hd_folder_tab, wrap=tk.WORD, height=10, state=tk.DISABLED)
hd_log_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

ef_folder_tab = tk.Frame(log_notebook)
log_notebook.add(ef_folder_tab, text="EF Folder Logs")
ef_log_area = scrolledtext.ScrolledText(ef_folder_tab, wrap=tk.WORD, height=10, state=tk.DISABLED)
ef_log_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

status_label = tk.Label(main_frame, text="Please select your input file and root folder.", relief="sunken", anchor="w", padx=5)
status_label.pack(side=tk.BOTTOM, pady=(5, 0), fill=tk.X)

app.mainloop()