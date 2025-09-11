import os
import re
import shutil
import sys
import subprocess

def find_holo_cine_files(identifiers, root_folder, progress_callback=None, error_callback=None):
    """
    Searches for .holo and .cine files based on a list of identifiers.
    Returns a list of unique, absolute file paths.
    """
    found_files = []
    top_level_dirs = [d for d in os.listdir(root_folder) if os.path.isdir(os.path.join(root_folder, d))]

    for i, identifier in enumerate(identifiers):
        prefix = identifier.split('_')[0]
        matching_top_dirs = [d for d in top_level_dirs if d.startswith(prefix)]

        if not matching_top_dirs:
            if error_callback:
                error_callback(f"[ERROR] No directory starting with '{prefix}' found for identifier '{identifier}'.")
            if progress_callback:
                progress_callback(i + 1)
            continue

        files_found_for_id = 0
        for dir_name in matching_top_dirs:
            target_dir_path = os.path.join(root_folder, dir_name)
            for dirpath, _, filenames in os.walk(target_dir_path):
                for filename in filenames:
                    if filename.startswith(identifier) and (filename.endswith('.holo') or filename.endswith('.cine')):
                        absolute_path = os.path.abspath(os.path.join(dirpath, filename))
                        found_files.append(absolute_path)
                        files_found_for_id += 1
        
        if files_found_for_id == 0:
            if error_callback:
                error_callback(f"[ERROR] No '.holo' or '.cine' files for '{identifier}' found in its matching directory/directories.")
        
        if progress_callback:
            progress_callback(i + 1)

    return sorted(list(set(found_files)))

def find_latest_hd_folders(holo_cine_files, error_callback=None):
    """
    Finds the latest HD folder for each of the given .holo/.cine files.
    Returns a tuple: (list of latest HD folders, list of files missing an HD folder).
    """
    latest_hd_folders = []
    missing_hd_files = []

    for file_path in holo_cine_files:
        directory = os.path.dirname(file_path)
        source_filename = os.path.basename(file_path)
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
            latest_folder_path = candidate_folders[max(candidate_folders.keys())]
            if latest_folder_path not in latest_hd_folders:
                latest_hd_folders.append(latest_folder_path)
        else:
            if error_callback:
                error_callback(f"[WARNING] For '{source_filename}', no corresponding HD folder was found.")
            missing_hd_files.append(file_path)
    
    return sorted(latest_hd_folders), sorted(missing_hd_files)

def find_latest_ef_folders(hd_folder_paths, error_callback=None):
    """
    Finds the latest EF folder within each given HD folder.
    Returns a tuple: (list of latest EF folders, list of HD folders missing an EF folder).
    """
    latest_ef_folders = []
    missing_ef_folders = []

    for hd_path in hd_folder_paths:
        eyeflow_dir = os.path.join(hd_path, "eyeflow")
        if not os.path.isdir(eyeflow_dir):
            if error_callback:
                error_callback(f"[WARNING] No 'eyeflow' directory found in: {hd_path}")
            missing_ef_folders.append(hd_path)
            continue

        hd_folder_name = os.path.basename(hd_path)
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
            latest_ef_folders.append(candidate_folders[max(candidate_folders.keys())])
        else:
            if error_callback:
                error_callback(f"[WARNING] 'eyeflow' directory exists but no EF folders found in: {hd_path}")
            missing_ef_folders.append(hd_path)
            
    return sorted(latest_ef_folders), sorted(missing_ef_folders)

def copy_ef_results(ef_folders, identifiers, destination_root, progress_callback=None, error_callback=None):
    """
    Copies PDF and JSON results from EF folders to a structured destination.
    """
    # Create all result directories first
    for identifier in identifiers:
        result_dir = os.path.join(destination_root, identifier)
        os.makedirs(os.path.join(result_dir, "pdf_reports"), exist_ok=True)
        os.makedirs(os.path.join(result_dir, "json"), exist_ok=True)

    copied_count = 0
    error_list = []

    for i, ef_folder in enumerate(ef_folders):
        ef_folder_name = os.path.basename(ef_folder)
        matched_identifier = next((iden for iden in identifiers if ef_folder_name.startswith(iden)), None)

        if not matched_identifier:
            error_msg = f"Could not match EF folder '{ef_folder_name}' to any input identifier."
            error_list.append(error_msg)
            if error_callback: error_callback(f"[EXPORT ERROR] {error_msg}")
            continue

        base_dest = os.path.join(destination_root, matched_identifier)
        pdf_dest = os.path.join(base_dest, "pdf_reports")
        json_dest = os.path.join(base_dest, "json")

        # Copy PDFs
        source_pdf_dir = os.path.join(ef_folder, 'pdf')
        if os.path.isdir(source_pdf_dir):
            for item in os.listdir(source_pdf_dir):
                source = os.path.join(source_pdf_dir, item)
                if os.path.isfile(source):
                    try:
                        shutil.copy2(source, pdf_dest)
                        copied_count += 1
                    except Exception as e:
                        error_list.append(f"Error copying '{source}': {e}")

        # Copy JSONs
        source_json_dir = os.path.join(ef_folder, 'json')
        if os.path.isdir(source_json_dir):
            for item in os.listdir(source_json_dir):
                if item.endswith('.json'):
                    source = os.path.join(source_json_dir, item)
                    try:
                        shutil.copy2(source, json_dest)
                        copied_count += 1
                    except Exception as e:
                        error_list.append(f"Error copying '{source}': {e}")
        
        if progress_callback:
            progress_callback(i + 1)
    
    return copied_count, error_list

def open_folder(folder_path):
    """Opens a folder in the default file explorer."""
    try:
        if sys.platform == "win32":
            os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", folder_path])
        else:
            subprocess.run(["xdg-open", folder_path])
        return True
    except Exception:
        return False