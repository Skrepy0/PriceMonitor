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


def get_current_options():
    resp = requests.get(f'{BASE_URL}/api/option/', headers=HEADERS)
    data = resp.json()
    options = {item['key']: item['value'] for item in data.get('data', [])}
    return options


def change_billing_expr(model: str, value: str) -> dict:
    options = get_current_options()

    current_exprs = json.loads(
        options.get('billing_setting.billing_expr') or '{}'
    )
    current_modes = json.loads(
        options.get('billing_setting.billing_mode') or '{}'
    )

    current_exprs[model] = value
    current_modes[model] = 'tiered_expr'

    raw_res = []
    for key, val in [
        ('billing_setting.billing_expr', json.dumps(current_exprs)),
        ('billing_setting.billing_mode', json.dumps(current_modes)),
    ]:
        payload = {'key': key, 'value': val}
        resp = requests.put(
            f'{BASE_URL}/api/option/', headers=HEADERS, json=payload
        )
        raw_res.append(resp.json())

    return {
        'success': raw_res[0]['success'] and raw_res[1]['success'],
        'message': raw_res[0]['message'] + raw_res[1]['message'],
    }


if __name__ == '__main__':
    value = 'len <= 512000 ? tier("tier_1", p * 0.3 + c * 1.2 + cr * 0.06) : tier("tier_2", p * 0.6 + c * 2.4 + cr * 0.12)'
    res = change_billing_expr('claude-fable-5', value)
    print(res)
