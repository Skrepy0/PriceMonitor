import json
import logging

import requests

from controller import BASE_URL, HEADERS
from data.station_price import (
    StationPriceData,
    StationPriceType,
    StationPriceOption,
)

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
