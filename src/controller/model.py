import json

import requests

from config import PRICE_RATIO
from controller import BASE_URL, HEADERS
from controller.price_setter import change_models_data
from controller.vendor import get_vendor_id_by_model, translate_vendor
from data.station_price import StationPriceData, PRICE_TYPES, StationPriceType


def format_endpoints(endpoints: list[str]) -> str:
    res = {}
    for endpoint in endpoints:
        res[endpoint] = True
    return json.dumps(res)


def add_new_model(
    upstream_price: dict,
    model_data: dict,
    station_price_data: StationPriceData,
    sync_official=0,
) -> dict:
    result = {
        'success': True,
        'msg': [],
        'advice': [],
        'already_exists': False,
    }
    model_name = model_data['model_name']
    model_vendor_id = model_data.get('vendor_id')
    vendor_id = translate_vendor(
        upstream_price['vendors'],
        station_price_data.get_price()['vendors'],
        model_vendor_id if model_vendor_id else -1,
    )
    if vendor_id == -1:
        vendor_id = get_vendor_id_by_model(model_data)
    model_payload = {
        'model_name': model_name,
        'vendor_id': vendor_id,
        'status': 1,
        'sync_official': sync_official,
        'enable_groups': model_data['enable_groups'],
        'endpoints': format_endpoints(model_data['supported_endpoint_types']),
    }
    icon = model_data.get('icon')
    if icon:
        model_payload['icon'] = icon
    resp = requests.post(
        f'{BASE_URL}/api/models/', json=model_payload, headers=HEADERS
    )
    if not resp.json()['success']:
        if resp.json()['message'] == '模型名称已存在':
            result['already_exists'] = True
            return result
        result['success'] = False
        result['msg'].append(resp.json())
        return result
    key_list = list(model_data.keys())
    data = []
    for price_type in PRICE_TYPES:
        if price_type.value in key_list:
            if (
                price_type == StationPriceType.MODEL_PRICE
                and model_data.get('quota_type') == 0
            ):
                continue
            item = {
                'key': price_type,
                'model': model_name,
                'value': model_data[price_type.value] * PRICE_RATIO,
            }
            data.append(item)

        else:
            if price_type == 'billing_expr':
                result['advice'].append(
                    f'请手动设置模型{model_name}的阶梯计费'
                )
    resp = change_models_data(
        data,
        station_price_data,
    )
    if not resp['success']:
        result['success'] = False
        result['msg'].append(resp['message'])

    return result
