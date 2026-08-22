import logging
from datetime import datetime
from typing import Dict, Any, Optional

from config import (
    PRICE_RELATED_KEYS,
    COMPARE_EXCLUDE_KEYS,
    PRICE_RATIO,
    GROUP_RATIO_RATIO,
    MAX_RATIO,
    MAX_BASE_PRICE,
)
from controller.group_setter import change_group_ratio
from controller.price_setter import change_models_data, change_billing_expr
from data.billing_exper import BillingExper
from data.station_price import (
    get_station_price_type_from_str,
    StationPriceData,
)

logger = logging.getLogger(__name__)
NOT_NUMBER_KEY = [
    'billing_expr',
    'billing_mode',
]


def group_ratio_compare(
    upstream_group_ratio: dict, station_group_ratio: dict
) -> Dict[str, Any]:
    """
    比较分组倍率，检查站点倍率是否低于上游。
    返回: {"has_abnormal": bool, "abnormal_group": [{"group": {"upstream_ratio": x, "station_ratio": y}}, ...]}
    """
    report = {'has_abnormal': False, 'abnormal_group': []}
    for group in station_group_ratio.keys():
        upstream_ratio = upstream_group_ratio.get(group)
        if upstream_ratio is None:
            continue
        station_ratio = station_group_ratio[group]
        if station_ratio < upstream_ratio:
            report['abnormal_group'].append(
                {
                    group: {
                        'upstream_ratio': upstream_ratio,
                        'station_ratio': station_ratio,
                    }
                }
            )
            report['has_abnormal'] = True
    return report


def auto_set_group_ratio(report: dict, station_price: dict) -> dict:
    """
    自动修正分组比率。
    返回:
    {
        "has_abnormal": bool,
        "abnormal_group": [
            {
                "group":
                 {
                    "upstream_ratio": x,
                    "station_ratio": y,
                    "auto_set_ratio": z|str
                 }
            },
            ...
        ]
    }
    """
    result = report
    if report['has_abnormal']:
        abnormal_group = report['abnormal_group']
        for i in range(len(abnormal_group)):
            group = abnormal_group[i]
            group_name = list(group.keys())[0]
            value = group[group_name]['upstream_ratio'] * GROUP_RATIO_RATIO
            response = change_group_ratio(group_name, value, station_price)
            if response is None:
                result['abnormal_group'][i][group_name]['auto_set_ratio'] = (
                    '修改失败!'
                )
                logger.warning(f'修改{group_name}倍率失败!')
            else:
                result['abnormal_group'][i][group_name]['auto_set_ratio'] = (
                    value
                )
    return result


def compare_billing_expr(upstream: str, station: str) -> bool:
    return BillingExper.compare_exprs(upstream, station)


def data_compare(upstream_data: list, station_data: list) -> Dict[str, Any]:
    """
    比较模型数据，检查站点定价是否低于上游。
    对于 billing_expr 字段，忽略双引号内的具体数值，只比较表达式结构。
    返回: {
        "has_abnormal": bool,
        "abnormal_group": [
            {
                "model_name": "xxx",
                "abnormal_fields": {"field1": {"upstream": val1, "station": val2}, ...}
            }
        ]
    }
    """
    report = {'has_abnormal': False, 'abnormal_group': []}

    upstream_data_dict = {}
    for model in upstream_data:
        new_dict = {}
        for key in model.keys():
            if key == 'model_name':
                continue
            if key in PRICE_RELATED_KEYS and key not in COMPARE_EXCLUDE_KEYS:
                new_dict[key] = model[key]
        upstream_data_dict[model['model_name']] = new_dict

    for model in station_data:
        model_name = model['model_name']
        upstream_model = upstream_data_dict.get(model_name)
        if upstream_model is None:
            continue

        abnormal_fields = {}
        for key in model.keys():
            if key in PRICE_RELATED_KEYS and key not in COMPARE_EXCLUDE_KEYS:
                station_val = model.get(key)
                upstream_val = upstream_model.get(key)

                if upstream_val is None:
                    continue

                is_abnormal = False

                if key in NOT_NUMBER_KEY:
                    if key == 'billing_expr':
                        if not compare_billing_expr(upstream_val, station_val):
                            is_abnormal = True
                    else:
                        if station_val != upstream_val:
                            is_abnormal = True
                else:
                    if isinstance(station_val, (int, float)) and isinstance(
                        upstream_val, (int, float)
                    ):
                        if station_val < upstream_val or (
                            upstream_val > MAX_BASE_PRICE
                            and station_val > upstream_val * MAX_RATIO
                        ):
                            is_abnormal = True
                    else:
                        if station_val != upstream_val:
                            is_abnormal = True

                if is_abnormal:
                    abnormal_fields[key] = {
                        'upstream': upstream_val,
                        'station': station_val,
                    }
        if (
            'billing_expr' in upstream_model.keys()
            and 'billing_expr' not in model.keys()
        ):
            abnormal_fields['billing_expr'] = {
                'upstream': upstream_model.get('billing_expr'),
                'station': '',
            }
        if abnormal_fields:
            report['abnormal_group'].append(
                {'model_name': model_name, 'abnormal_fields': abnormal_fields}
            )
            report['has_abnormal'] = True

    return report


def auto_set_price(
    abnormal_report: dict, station_price_data: dict
) -> Dict[str, Any]:
    """
    自动修正模型价格字段。
    对于 billing_expr 字段，无法自动修复, 发送信息提醒管理员手动修复
    返回: {
        "has_abnormal": bool,
        "abnormal_group": [
            {
                "model_name": "xxx",
                "abnormal_fields": {
                    "field1": {
                        "upstream": val1,
                        "station": val2,
                        "auto_set_price": val3|str
                    },
                    ...
                }
            }
        ]
    }
    """
    result = abnormal_report
    if abnormal_report['has_abnormal']:
        abnormal_groups = abnormal_report['abnormal_group']
        data = []
        for i in range(len(abnormal_groups)):
            group = abnormal_groups[i]
            model_name = group['model_name']
            abnormal_fields = group['abnormal_fields']

            for key, value in abnormal_fields.items():
                station_price_type = get_station_price_type_from_str(key)
                if station_price_type is not None:
                    auto_set: float = value['upstream'] * PRICE_RATIO
                    item = {
                        'key': station_price_type,
                        'value': auto_set,
                        'model': model_name,
                    }
                    data.append(item)
                    result['abnormal_group'][i]['abnormal_fields'][key][
                        'auto_set_price'
                    ] = auto_set
                else:
                    if key == 'billing_expr':
                        upstream_expr = value.get('upstream')
                        station_expr = value.get('station')
                        corrected = BillingExper.correct_station_expr(
                            upstream_expr, station_expr
                        )
                        res = change_billing_expr(model_name, corrected)
                        result['abnormal_group'][i]['abnormal_fields'][key][
                            'auto_set_price'
                        ] = (
                            corrected
                            if res['success']
                            else f'修改失败,请手动修复{res["message"]}'
                        )
                    else:
                        logger.warning(
                            '暂不支持自动修改此类型数据, 请手动修复'
                        )
                        result['abnormal_group'][i]['abnormal_fields'][key][
                            'auto_set_price'
                        ] = '需手动'
        response = change_models_data(
            data,
            StationPriceData(station_price_data),
        )
        if not response['success']:
            logger.warning('自动修改模型数据失败,请手动修复')
            for key in result['abnormal_group'][i]['abnormal_fields'].keys():
                result['abnormal_group'][i]['abnormal_fields'][key][
                    'auto_set_price'
                ] = '修改失败!'
    return result


def compare_and_build_report(
    upstream_price: dict, station_price: dict
) -> Optional[str]:
    upstream_data = upstream_price.get('data', [])
    station_data = station_price.get('data', [])
    group_ratio_up = upstream_price.get('group_ratio', {})
    group_ratio_st = station_price.get('group_ratio', {})

    html_parts = []

    model_report = auto_set_price(
        data_compare(upstream_data, station_data), station_price
    )
    if model_report['has_abnormal']:
        html_parts.append(
            '<h3 style="color: #dc3545; margin-top: 0;">⚠️ 模型定价异常</h3>'
        )
        html_parts.append(
            '<table style="border-collapse: collapse; width: 100%; font-size: 14px; margin-bottom: 16px;">'
        )
        html_parts.append("""
            <tr style="background: #343a40; color: white;">
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">模型名称</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">异常字段</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">上游值</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">站点值</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">自动修改后的值</th>
            </tr>
        """)
        for item in model_report['abnormal_group']:
            model_name = item['model_name']
            fields = item['abnormal_fields']
            rowspan = len(fields)
            for idx, (field, values) in enumerate(fields.items()):
                upstream_val = values['upstream']
                station_val = values['station']
                auto_set_val = values['auto_set_price']
                # 标记异常方向（红色表示偏低）
                color = (
                    '#dc3545'
                    if isinstance(station_val, (int, float))
                    and station_val < upstream_val
                    else '#856404'
                )
                auto_set_color = (
                    '#e43d30'
                    if not isinstance(auto_set_val, (int, float))
                    else '#52a535'
                )
                html_parts.append(f"""
                    <tr>
                        {f'<td style="padding: 8px 12px; border: 1px solid #dee2e6; vertical-align: middle;" rowspan="{rowspan}">{model_name}</td>' if idx == 0 else ''}
                        <td style="padding: 8px 12px; border: 1px solid #dee2e6;"><code>{field}</code></td>
                        <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{upstream_val}</td>
                        <td style="padding: 8px 12px; border: 1px solid #dee2e6; color: {color}; font-weight: bold;">{station_val}</td>
                        <td style="padding: 8px 12px; border: 1px solid #dee2e6; color: {auto_set_color}; font-weight: bold;">{auto_set_val}</td>
                    </tr>
                """)
        html_parts.append('</table>')

    if group_ratio_up and group_ratio_st:
        ratio_report = auto_set_group_ratio(
            group_ratio_compare(group_ratio_up, group_ratio_st), station_price
        )
        if ratio_report['has_abnormal']:
            html_parts.append(
                '<h3 style="color: #dc3545; margin-top: 0;">⚠️ 分组倍率异常</h3>'
            )
            html_parts.append(
                '<table style="border-collapse: collapse; width: 100%; font-size: 14px; margin-bottom: 16px;">'
            )
            html_parts.append("""
                <tr style="background: #343a40; color: white;">
                    <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">分组名称</th>
                    <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">上游倍率</th>
                    <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">站点倍率</th>
                    <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">自动修改后倍率</th>
                </tr>
            """)
            for item in ratio_report['abnormal_group']:
                for group, values in item.items():
                    html_parts.append(f"""
                        <tr>
                            <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{
                        group
                    }</td>
                            <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{
                        values['upstream_ratio']
                    }</td>
                            <td style="padding: 8px 12px; border: 1px solid #dee2e6; color: #dc3545; font-weight: bold;">{
                        values['station_ratio']
                    }</td>
                            <td style="padding: 8px 12px; border: 1px solid #dee2e6; color: {
                        (
                            '#e43d30'
                            if not isinstance(
                                values['auto_set_ratio'], (int, float)
                            )
                            else '#52a535'
                        )
                    }; font-weight: bold;">{values['auto_set_ratio']}</td>
                        </tr>
                    """)
            html_parts.append('</table>')

    if not html_parts:
        return None

    header = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; background: #fff5f5; border-radius: 8px; border: 1px solid #f5c6cb; max-width: 900px;">
        <h2 style="color: #721c24; margin-top: 0;">📊 价格异常报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</h2>
        <p style="color: #721c24;">以下检测到站点定价低于上游官方价格，请及时核实。</p>
        <hr style="border: 1px solid #f5c6cb;">
    """

    return header + '\n'.join(html_parts) + '</div>'
