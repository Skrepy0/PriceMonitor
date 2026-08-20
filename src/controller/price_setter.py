import json
import logging
from typing import List

import requests

from controller import BASE_URL, HEADERS
from data.station_price import (
    StationPriceData,
    StationPriceType,
    StationPriceOption,
)
from monitor.station import get_station_price

logger = logging.getLogger(__name__)


def update_option(key: StationPriceOption, value) -> dict:
    url = f'{BASE_URL}/api/option/'
    payload = {'key': key.value, 'value': value}
    resp = requests.put(url, json=payload, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def change_model_data(
    key: StationPriceType,
    model: str,
    value: float,
    station_price_data: StationPriceData,
) -> dict:
    station_price_data.change_value(key, model, value)
    return update_option(
        key.option,
        json.dumps(
            station_price_data.formatted_station_price()[key],
            ensure_ascii=False,
        ),
    )


def change_models_data(
    data: List[dict],
    station_price_data: StationPriceData,
) -> dict:
    result = {'success': True, 'message': ''}
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


if __name__ == '__main__':
    res = change_model_data(
        StationPriceType.COMPLETION_RATIO,
        'claude-fable-5',
        value=1.54,
        station_price_data=StationPriceData(get_station_price()),
    )
    print(res)
