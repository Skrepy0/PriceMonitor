import json
import logging

import requests

from config import STATION_URL, STATION_TOKEN
from data.station_price import (
    StationPriceData,
    StationPriceType,
    StationPriceOption,
)

logger = logging.getLogger(__name__)
BASE_URL = STATION_URL
ACCESS_TOKEN = STATION_TOKEN


def update_option(key: StationPriceOption, value) -> dict:
    url = f'{BASE_URL}/api/option/'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {ACCESS_TOKEN}',  # 或使用 New-API-User / Cookie，取决于你的鉴权方式
    }
    payload = {'key': key.value, 'value': value}
    resp = requests.put(url, json=payload, headers=headers)
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
