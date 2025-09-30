# memory.py
import json, os
from typing import List, Dict

DATA_DIR = "./.sessions"
os.makedirs(DATA_DIR, exist_ok=True)

class Memory:
    def __init__(self, session_id: str):
        self.path = os.path.join(DATA_DIR, f"{session_id}.json")

    def load(self) -> List[Dict[str, str]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, messages: list) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
