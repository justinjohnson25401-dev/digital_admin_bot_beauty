
import json
import os

def load_config(path: str) -> dict:
    config = {}
    for filename in os.listdir(path):
        if filename.endswith('.json'):
            with open(os.path.join(path, filename), 'r', encoding='utf-8') as f:
                config.update(json.load(f))
    return config
