import json
import logging

import requests

from config import STATION_URL, STATION_TOKEN

logger = logging.getLogger(__name__)
BASE_URL = STATION_URL
ACCESS_TOKEN = STATION_TOKEN


def update_group_ratio(data: dict) -> dict:
    url = f'{BASE_URL}/api/option/'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }
    payload = {
        'key': 'GroupRatio',
        'value': json.dumps(data, ensure_ascii=False),
    }
    resp = requests.put(url, json=payload, headers=headers)
    return resp.json()


def change_group_ratio(
    group: str, value: float, station_price: dict
) -> dict | None:
    group_ratio = station_price['group_ratio']
    if group not in group_ratio.keys():
        logger.warning(f'价格分组 {group} 在 {group_ratio} 中未找到!')
        return None
    else:
        group_ratio[group] = value
        response = update_group_ratio(group_ratio)
        if not response['success']:
            logger.warning('价格分组设置失败:', response)
            return None
        return response
