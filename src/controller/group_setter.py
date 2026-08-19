import json
import logging

import requests

from controller import HEADERS
from controller.price_setter import BASE_URL

logger = logging.getLogger(__name__)


def update_group_ratio(data: dict) -> dict:
    url = f'{BASE_URL}/api/option/'
    payload = {
        'key': 'GroupRatio',
        'value': json.dumps(data, ensure_ascii=False),
    }
    resp = requests.put(url, json=payload, headers=HEADERS)
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
