import os
import json

CONFIG_FILE = "config.json"

def load_config():
    """Load configuration from config.json."""
    if not os.path.exists(CONFIG_FILE):
        print(f"[!] Error: {CONFIG_FILE} not found. Please create it.")
        return None
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)
