import os
import json
from datetime import datetime

def create_session_paths(subject_id, base_dir="data/sessions"):
    """
    Creates a new session folder and returns the full path.
    Example: data/sessions/S01_SUBJ001_YYYYMMDD/
    """
    date_str = datetime.now().strftime("%Y%m%d")
    # A simple way to handle session number, could be more robust
    session_num = len(os.listdir(base_dir)) + 1
    session_id = f"S{session_num:02d}_{subject_id}_{date_str}"
    session_path = os.path.join(base_dir, session_id)
    
    os.makedirs(os.path.join(session_path, 'raw'), exist_ok=True)
    os.makedirs(os.path.join(session_path, 'processed'), exist_ok=True)
    os.makedirs(os.path.join(session_path, 'meta'), exist_ok=True)
    
    # Create an initial metadata file
    meta = {
        "subject_id": subject_id,
        "session_id": session_id,
        "date": datetime.utcnow().isoformat(),
        "devices_used": ["Polar H10"],
        "notes": ""
    }
    with open(os.path.join(session_path, 'meta', 'session_metadata.json'), 'w') as f:
        json.dump(meta, f, indent=4)
        
    return session_path