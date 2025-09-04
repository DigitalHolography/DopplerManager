
import os
import re
import sqlite3
import json
from collections import defaultdict
from hashlib import sha256

def extract_last_block_between_bars(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find indices of lines that are bars (lines containing only '=' chars)
    bar_lines = [i for i, line in enumerate(lines) if line.strip() and set(line.strip()) == {'='}]
    
    if len(bar_lines) < 2:
        return None  # Not enough bars to form a block
    
    # Get the last two bars to find the last block
    start = bar_lines[-2]
    end = bar_lines[-1]
    
    # Extract lines between the bars (excluding the bars themselves)
    block_lines = lines[start+1:end]
    
    # Join and strip trailing spaces/newlines
    return ''.join(block_lines).strip()

def get_file_name_without_hd(folder_path):
    # Get the base name of the file from the folder path
    file_name = os.path.basename(folder_path)

    # Find the index of '_HD_'
    hd_index = file_name.find('_HD_')

    if hd_index != -1:
        # Slice the string up to '_HD_'
        file_name = file_name[:hd_index]

    return file_name


def get_name_after_hd(file_path):
    # Get the base name of the file from the file path
    file_name = os.path.basename(file_path)

    # Use regular expression to find the pattern HD_[any number]_
    match = re.search(r'HD_\d+_', file_name)

    if match:
        # Extract the part after the matched pattern
        name_after_hd = file_name[match.end():]
        # Remove the file extension
        name_after_hd = os.path.splitext(name_after_hd)[0]
        return name_after_hd
    else:
        return None
    


def group_ef_counts_by_shared_metadata(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Load all hd_data entries
    c.execute("SELECT id, version_text, rendering_parameters FROM hd_data")
    hd_rows = c.fetchall()

    # Map from hd_id to metadata group key
    hd_group_keys = {}

    for hd_id, version, rendering_json in hd_rows:
        # Normalize and hash the rendering parameters
        try:
            rendering_obj = json.loads(rendering_json) if rendering_json else {}
        except json.JSONDecodeError:
            rendering_obj = {}

        rendering_hash = sha256(json.dumps(rendering_obj, sort_keys=True).encode()).hexdigest()
        version_hash = version

        # Get all EF JSON parameters for this HD
        c.execute("""
            SELECT json_content,json_name FROM ef_jsons
            JOIN ef_data ON ef_data.id = ef_jsons.ef_id
            WHERE ef_data.hd_id = ? AND json_name = 'InputEyeFlowParams.json'
        """, (hd_id,))
        ef_jsons = [row[0] for row in c.fetchall()]

        # Aggregate eyeflow parameters (InputParameters.json under ef_jsons)
        eyeflow_params = []
        for j in ef_jsons:
            try:
                obj = json.loads(j)
                eyeflow_params.append(obj)
            except:
                continue

        # Hash the sorted JSON list as string to use as key
        eyeflow_hash = sha256(json.dumps(eyeflow_params, sort_keys=True).encode()).hexdigest()

        # You can define the measure tag uniquely, e.g., from path or EF folder names:
        c.execute("SELECT ef_folder FROM ef_data WHERE hd_id = ?", (hd_id,))
        ef_folders = [row[0] for row in c.fetchall()]
        measure_tag = sha256("".join(sorted(ef_folders)).encode()).hexdigest()

        # Create a grouping key
        group_key = (version_hash, rendering_hash, eyeflow_hash, measure_tag)
        hd_group_keys[hd_id] = group_key

    # Count EF folders by group
    group_counts = defaultdict(int)

    for hd_id, group_key in hd_group_keys.items():
        c.execute("SELECT COUNT(*) FROM ef_data WHERE hd_id = ?", (hd_id,))
        ef_count = c.fetchone()[0]
        group_counts[group_key] += ef_count

    conn.close()

    # Output as a list of dictionaries
    return [
        {
            "version_hash": k[0],
            "rendering_hash": k[1],
            "eyeflow_hash": k[2],
            "measure_tag": k[3],
            "ef_count": v
        }
        for k, v in group_counts.items()
    ]
