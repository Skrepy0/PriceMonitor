import json

import requests

from config import PRICE_RATIO
from controller import BASE_URL, HEADERS
from controller.price_setter import change_model_data
from controller.vendor import get_vendor_id_by_model
from data.station_price import StationPriceData, PRICE_TYPES, StationPriceType
from monitor.station import get_station_price


def format_endpoints(endpoints: list[str]) -> str:
    res = {}
    for endpoint in endpoints:
        res[endpoint] = True
    return json.dumps(res)


def add_new_model(
    model_data: dict, station_price_data: StationPriceData, sync_official=0
) -> dict:
    result = {'success': True, 'msg': []}
    model_name = model_data['model_name']
    vendor_id = get_vendor_id_by_model(model_data)
    status = 1
    if vendor_id == -1:
        status = 0
        result['success'] = False
        result['msg'].append(
            'Vendor ID 没有自动匹配到, 使用默认id, 模型状态自动设置为0, 请管理员手动解决!'
        )
    model_payload = {
        'model_name': model_name,
        'vendor_id': vendor_id,
        'status': status,
        'sync_official': sync_official,
        'enable_groups': model_data['enable_groups'],
        'endpoints': format_endpoints(model_data['supported_endpoint_types']),
    }
    resp = requests.post(
        f'{BASE_URL}/api/models/', json=model_payload, headers=HEADERS
    )
    if not resp.json()['success']:
        result['success'] = False
        result['msg'].append(resp.json())
        return result
    key_list = list(model_data.keys())

    for price_type in PRICE_TYPES:
        if price_type.value in key_list:
            if (
                model['quota_type'] == 0
                and price_type == StationPriceType.MODEL_PRICE
            ):
                continue
            resp = change_model_data(
                price_type,
                model_name,
                model_data[price_type.value] * PRICE_RATIO,
                station_price_data,
            )
            if not resp['success']:
                result['success'] = False
                result['msg'].append(resp['msg'])
    return result


if __name__ == '__main__':
    model = {
        'model_name': 'mimo-v2-omni',
        'quota_type': 0,
        'model_ratio': 37.5,
        'model_price': 0,
        'owner_by': '',
        'completion_ratio': 1,
        'enable_groups': ['国模丨先进模型'],
        'supported_endpoint_types': ['openai'],
    }
    response = add_new_model(model, StationPriceData(get_station_price()))
    print(response)
