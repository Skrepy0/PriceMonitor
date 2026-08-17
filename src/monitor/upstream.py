import logging

import requests

from config import UPSTREAM_TOKEN, UPSTREAM_URL
from store.json import save_json

logger = logging.getLogger(__name__)
base_url = UPSTREAM_URL if UPSTREAM_URL.endswith('/') else UPSTREAM_URL + '/'
token = UPSTREAM_TOKEN
headers = {'Authorization': f'Bearer {token}'}


def get_upstream_price():
    logging.info('正在获取上游价格')
    response = requests.get(f'{base_url}api/pricing', headers=headers)
    if response.status_code == 200:
        logging.info('获取上游价格成功')
        price_json = response.json()
        save_json(price_json, 'upstream_price')
        return response.json()
    return None
