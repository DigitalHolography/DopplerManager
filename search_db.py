from Tools.utils import *
import json
with open("eyeflow_db_request_summary.json", "w") as f:
    json.dump(group_ef_counts_by_shared_metadata("collected_data.db"), f, indent=2)