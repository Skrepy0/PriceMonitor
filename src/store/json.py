import json
from pathlib import Path

from config import PRICE_DATA_SAVE_PATH, LOG_SAVE_PATH


def init():
    # 初始化目录
    Path(PRICE_DATA_SAVE_PATH).mkdir(parents=True, exist_ok=True)
    Path(LOG_SAVE_PATH).mkdir(parents=True, exist_ok=True)


def save_json(data: dict, file_name: str):
    path = Path(PRICE_DATA_SAVE_PATH) / f'{file_name}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_json(file_name: str, default=None):
    path = Path(PRICE_DATA_SAVE_PATH) / f'{file_name}.json'
    if not path.exists():
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
