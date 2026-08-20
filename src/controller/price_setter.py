import json
import logging
from typing import List

import requests

from controller import BASE_URL, HEADERS
from data.station_price import (
    StationPriceData,
    StationPriceOption,
)

logger = logging.getLogger(__name__)


def update_option(key: StationPriceOption, value) -> dict:
    url = f'{BASE_URL}/api/option/'
    payload = {'key': key.value, 'value': value}
    resp = requests.put(url, json=payload, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def change_models_data(
    data: List[dict],
    station_price_data: StationPriceData,
) -> dict:
    result = {'success': True, 'message': ''}
    if not station_price_data.is_available:
        result['success'] = False
        result['message'] = 'Station price is not available'
        return result

    for item in data:
        key = item['key']
        station_price_data.change_value(key, item['model'], item['value'])
        response = update_option(
            key.option,
            json.dumps(
                station_price_data.formatted_station_price()[key],
                ensure_ascii=False,
            ),
        )
        result['message'] += response['message']
        result['success'] = response['success'] and result['success']
    return result
