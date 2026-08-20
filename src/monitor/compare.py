import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional

from config import (
    PRICE_RELATED_KEYS,
    COMPARE_EXCLUDE_KEYS,
    PRICE_RATIO,
    GROUP_RATIO_RATIO,
)
from controller.group_setter import change_group_ratio
from controller.price_setter import change_models_data
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


def _extract_variable_coeffs(expr: str) -> Dict[str, float]:
    """
    从表达式中提取变量 -> 系数 映射。
    仅处理计费部分的算术项，忽略条件。
    """
    # 移除字符串内容（如 tier 的标签）
    expr = re.sub(r'"[^"]*"', '', expr)
    # 查找乘法项：var * num 或 num * var
    pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\*\s*(\d+\.?\d*)|(\d+\.?\d*)\s*\*\s*([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(pattern, expr)
    coeffs = {}
    for m in matches:
        if m[0] and m[1]:
            var, coeff = m[0], float(m[1])
        elif m[2] and m[3]:
            var, coeff = m[3], float(m[2])
        else:
            continue
        coeffs[var] = coeffs.get(var, 0) + coeff
    # 处理单独的变量（系数为1），比如 "p + c"
    all_vars = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expr))
    for var in all_vars:
        if var not in coeffs:
            coeffs[var] = coeffs.get(var, 0) + 1
    return coeffs


def compare_billing_expr(upstream: str, station: str) -> bool:
    """
    比较 billing_expr，返回 True 表示站点定价不低于上游（无异常）。

    规则：
      1. 如果存在 '?'，则 '?' 之前的部分（条件）必须完全相同。
      2. 计费部分（'?' 之后，若无 '?' 则为整个表达式）：
          - 上游每个变量的系数，下游必须有且 >= 上游。
          - 下游可以有额外变量（视为正常）。
    """
    if not upstream or not station:
        return True

    # 1. 处理条件部分（仅在存在 '?' 时比较）
    def split_expr(expr: str):
        if '?' in expr:
            cond, pricing = expr.split('?', 1)
            return cond.strip(), pricing.strip()
        else:
            return None, expr.strip()

    up_cond, up_pricing = split_expr(upstream)
    st_cond, st_pricing = split_expr(station)

    if up_cond is not None and st_cond is not None:
        if up_cond != st_cond:
            return False
    elif up_cond is not None or st_cond is not None:
        # 一个有一个没有，视为不一致
        return False

    # 2. 提取并比较计费部分的系数
    up_coeffs = _extract_variable_coeffs(up_pricing)
    st_coeffs = _extract_variable_coeffs(st_pricing)

    for var, coeff in up_coeffs.items():
        if var not in st_coeffs:
            return False
        if st_coeffs[var] < coeff:
            return False

    return True


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
                        if station_val < upstream_val:
                            is_abnormal = True
                    else:
                        if station_val != upstream_val:
                            is_abnormal = True

                if is_abnormal:
                    abnormal_fields[key] = {
                        'upstream': upstream_val,
                        'station': station_val,
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
                    logger.warning('暂不支持自动修改此类型数据, 请手动修复')
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
