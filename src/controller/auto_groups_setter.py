import json
import logging

import requests

from controller import BASE_URL, HEADERS

logger = logging.getLogger(__name__)

url = f'{BASE_URL}/api/option/'


def update_group_order(new_order: list[str]) -> dict:
    payload = {
        'key': 'AutoGroups',
        'value': json.dumps(new_order),
    }

    resp = requests.put(url, json=payload, headers=HEADERS)
    return resp.json()
