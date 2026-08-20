import json
import logging
from typing import Any

from config import GROUP_RATIO_RATIO
from controller.auto_groups_setter import update_group_order
from controller.group_setter import create_new_group
from controller.model import add_new_model
from data.station_price import StationPriceData

logger = logging.getLogger(__name__)


def _result(success: bool = True) -> dict[str, Any]:
    return {'success': success, 'message': []}


def _merge_result(
    target: dict[str, Any], source: dict[str, Any], prefix: str = ''
) -> None:
    if not source:
        return
    if not source.get('success', True):
        target['success'] = False
    messages = source.get('message') or source.get('msg')
    if messages:
        if isinstance(messages, list):
            target['message'].extend([f'{prefix}{m}' for m in messages])
        else:
            target['message'].append(f'{prefix}{messages}')


def _station_payload(station_price: dict) -> StationPriceData:
    return StationPriceData(station_price)


def _step_result(step: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {'success': True, 'step': step, 'items': items}


def _flatten_result(payload: Any) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, list):
        rows = []
        for item in payload:
            rows.extend(_flatten_result(item))
        return rows
    if isinstance(payload, dict):
        if 'msg' in payload and isinstance(payload['msg'], list):
            return [str(item) for item in payload['msg']]
        return [json.dumps(payload, ensure_ascii=False, default=str)]
    return [str(payload)]


def update_groups(upstream_price: dict, station_price: dict) -> dict:
    items = []
    upstream_groups = upstream_price.get('usable_group', {}) or {}
    station_groups = station_price.get('usable_group', {}) or {}

    for group_name, desc in upstream_groups.items():
        if group_name in station_groups:
            continue
        create_result = create_new_group(
            group_name,
            ratio=upstream_price['group_ratio'][group_name]
            * GROUP_RATIO_RATIO,
            desc=desc,
        )
        items.append(
            {
                'name': group_name,
                'description': desc,
                'action': 'create_group',
                'success': bool(create_result.get('success', False)),
                'result': create_result,
            }
        )
    return _step_result('groups', items)


def update_model(upstream_price: dict, station_price: dict) -> dict:
    items = []
    station_price_data = _station_payload(station_price)
    upstream_models = upstream_price.get('data', []) or []
    station_models = {
        model.get('model_name')
        for model in station_price.get('data', []) or []
    }

    for model_data in upstream_models:
        model_name = model_data.get('model_name')
        if not model_name or model_name in station_models:
            continue
        add_result = add_new_model(model_data, station_price_data)
        items.append(
            {
                'name': model_name,
                'action': 'create_model',
                'success': bool(add_result.get('success', False)),
                'result': add_result,
            }
        )
    return _step_result('models', items)


def update_auto_groups(upstream_price: dict, station_price: dict) -> dict:
    upstream_auto_groups = upstream_price.get('auto_groups', []) or []
    station_auto_groups = station_price.get('auto_groups', []) or []

    merged = list(station_auto_groups)
    for group_name in upstream_auto_groups:
        if group_name not in merged:
            merged.append(group_name)

    items = []
    if merged != list(station_auto_groups):
        update_result = update_group_order(merged)
        items.append(
            {
                'name': 'AutoGroups',
                'action': 'update_order',
                'success': bool(update_result.get('success', False)),
                'result': update_result,
                'value': merged,
            }
        )
    return _step_result('auto_groups', items)


def update(upstream_price: dict, station_price: dict) -> dict:
    result = _result()
    steps = []
    for updater in (update_groups, update_model, update_auto_groups):
        step_result = updater(upstream_price, station_price)
        steps.append(step_result)
        if not step_result.get('success', True):
            result['success'] = False
        result['message'].append(step_result)
    result['steps'] = steps
    return result
