import json
import logging

import requests

from controller import HEADERS
from controller.price_setter import BASE_URL

logger = logging.getLogger(__name__)


def update_option(key: str, value: str) -> dict:
    resp = requests.put(
        f'{BASE_URL}/api/option/',
        headers=HEADERS,
        json={'key': key, 'value': value},
    )
    return resp.json()


def update_group_ratio(data: dict) -> dict:
    return update_option('GroupRatio', json.dumps(data, ensure_ascii=False))


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


def create_new_group(
    name: str, ratio: float = 1, topup_ratio: float = 1, desc: str = ''
) -> dict:
    result = {'success': True, 'msg': []}

    options_resp = requests.get(f'{BASE_URL}/api/option/', headers=HEADERS)
    res1 = options_resp.json()
    if not res1['success']:
        result['success'] = False
        result['msg'].append('获取options时失败' + res1['msg'])
        return result

    options = {o['key']: o['value'] for o in options_resp.json()['data']}

    new_group = name

    user_usable_groups = json.loads(options.get('UserUsableGroups', '{}'))
    user_usable_groups[new_group] = desc
    res2 = update_option(
        'UserUsableGroups', json.dumps(user_usable_groups, ensure_ascii=False)
    )
    if not res2['success']:
        result['success'] = False
        result['msg'].append(
            '设置UserUsableGroups时失败, 请管理员手动设置:' + res2['msg']
        )
    group_ratio = json.loads(options.get('GroupRatio', '{}'))
    group_ratio[new_group] = ratio
    res3 = update_option(
        'GroupRatio', json.dumps(group_ratio, ensure_ascii=False)
    )
    if not res3['success']:
        result['success'] = False
        result['msg'].append(
            '设置GroupRatio时失败, 请管理员手动设置:' + res3['msg']
        )

    topup_group_ratio = json.loads(options.get('TopupGroupRatio', '{}'))
    topup_group_ratio[new_group] = topup_ratio
    res4 = update_option(
        'TopupGroupRatio', json.dumps(topup_group_ratio, ensure_ascii=False)
    )
    if not res4['success']:
        result['success'] = False
        result['msg'].append(
            '设置TopupGroupRatio时失败, 请管理员手动设置:' + res4['msg']
        )
    return result
