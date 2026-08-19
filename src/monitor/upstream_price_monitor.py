import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from config import PRICE_RELATED_KEYS
from monitor.compare import compare_and_build_report
from monitor.station import get_station_price
from monitor.upstream import get_upstream_price
from remind.sender import send_email
from store.json import get_json, save_json

logger = logging.getLogger(__name__)

station_price = get_station_price()


async def monitor_upstream_price():
    if station_price is None:
        logger.warning('站点价格获取失败, 跳过本次检查!')
        return
    try:
        old_price = get_json('upstream_price')
        if not old_price:
            upstream_price = get_upstream_price()
            logger.info(
                '首次运行，已保存价格快照，上游价格更新检查, 准备进行站点价格比较'
            )
            report = compare_and_build_report(
                upstream_price=upstream_price, station_price=station_price
            )
            if report is not None:
                logger.info('检测到站点定价异常，发送邮件通知')
                await send_email(report)
            logger.info('站点定价正常')
            return

        new_price = get_upstream_price()
        if not new_price:
            logger.warning('上游价格获取失败')
            return

        logger.info('上游价格获取成功')

        report = build_change_report(old_price, new_price)

        save_json(new_price, 'upstream_price')

        if report is None:
            logger.info('价格无变化, 定价无异常')
        else:
            await send_email(report)

    except Exception as e:
        logger.error('监控任务执行异常: %s', e, exc_info=True)


def build_change_report(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    old_version = old_price.get('pricing_version', '未知')
    new_version = new_price.get('pricing_version', '未知')
    compare_report = compare_and_build_report(
        upstream_price=new_price, station_price=station_price
    )

    reports = []
    diff_functions = [
        (
            '自动分组(索引从0开始)',
            lambda: format_auto_groups_diff(old_price, new_price),
        ),
        ('模型数据', lambda: format_data_diff(old_price, new_price)),
        ('分组倍率', lambda: format_group_ratio_diff(old_price, new_price)),
        ('可用分组', lambda: format_usable_group_diff(old_price, new_price)),
    ]

    for name, func in diff_functions:
        result = func()
        if result:
            reports.append(f'<h3>【{name}】</h3>\n{result}')

    if not reports:
        if compare_report is not None:
            logger.info('检测到定价异常')
            return compare_report
        return None

    header = build_report_header(old_version, new_version)
    body = '\n\n'.join(reports)
    if compare_report is not None:
        logger.info('检测到价格变动和定价异常')
        body += f'\n\n<hr style="border: 2px dashed #dc3545; margin: 20px 0;">\n{compare_report}'
    return f'{header}\n\n{body}'


def build_report_header(old_version: str, new_version: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa; border-radius: 8px;">
        <h2 style="color: #2c3e50;">📊 价格变动报告</h2>
        <p><strong>生成时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>旧版本:</strong> <code>{old_version}</code></p>
        <p><strong>新版本:</strong> <code>{new_version}</code></p>
        <hr style="border: 1px solid #dee2e6;">
    </div>
    """


def format_auto_groups_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    old_list = old_price.get('auto_groups', [])
    new_list = new_price.get('auto_groups', [])

    if old_list == new_list:
        return None

    lines = ['<ul style="list-style-type: none; padding-left: 0;">']
    len1, len2 = len(old_list), len(new_list)

    for i in range(min(len1, len2)):
        if old_list[i] != new_list[i]:
            lines.append(
                f'  <li style="padding: 4px 0;">索引 {i}: '
                f'<span style="color: #dc3545;">{old_list[i]}</span> → '
                f'<span style="color: #28a745;">{new_list[i]}</span></li>'
            )

    if len1 > len2:
        lines.append(
            f'  <li style="color: #dc3545;">被移除: {old_list[len2:]}</li>'
        )
    elif len2 > len1:
        lines.append(
            f'  <li style="color: #28a745;">新增: {new_list[len1:]}</li>'
        )

    lines.append('</ul>')
    return '\n'.join(lines) if len(lines) > 2 else None


def format_data_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    diff = data_compare(old_price, new_price)
    if not diff:
        return None

    added = diff.get('added', [])
    removed = diff.get('removed', [])
    modified = diff.get('modified', [])

    html = f"""
    <div style="font-family: Arial, sans-serif;">
        <p><strong>新增:</strong> {len(added)} 个 &nbsp;|&nbsp; 
           <strong>移除:</strong> {len(removed)} 个 &nbsp;|&nbsp; 
           <strong>修改:</strong> {len(modified)} 个</p>
    """

    # 移除的模型
    if removed:
        names = [item.get('model_name', '未知') for item in removed]
        html += f'<p><span style="color: #dc3545;">移除的模型:</span> {", ".join(names)}</p>'

    # 新增模型
    if added:
        html += '<p><strong style="color: #28a745;">新增模型:</strong></p><ul>'
        for item in added:
            name = item.get('model_name', '未知')
            vendor = item.get('vendor_id', '?')
            ratio = item.get('model_ratio', '?')
            comp = item.get('completion_ratio', '?')
            html += f'<li>{name} (vendor={vendor}, ratio={ratio}, comp={comp})</li>'
        html += '</ul>'

    # 修改模型
    if modified:
        html += """
        <p><strong style="color: #ffc107;">修改详情:</strong></p>
        <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
            <tr style="background: #343a40; color: white;">
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">模型</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">字段</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">旧值</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">新值</th>
            </tr>
        """
        for m in modified:
            name = m.get('model_name', '未知')
            fields = m.get('changed_fields', [])
            old_item = m.get('old', {})
            new_item = m.get('new', {})
            row_span = len(fields)
            for idx, f in enumerate(fields):
                old_val = old_item.get(f, '无')
                new_val = new_item.get(f, '无')
                # 标记数值变化方向
                color = ''
                if isinstance(new_val, (int, float)) and isinstance(
                    old_val, (int, float)
                ):
                    color = (
                        'color: #28a745;'
                        if new_val > old_val
                        else 'color: #dc3545;'
                        if new_val < old_val
                        else ''
                    )
                html += f"""
                <tr>
                    {f'<td style="padding: 8px 12px; border: 1px solid #dee2e6;" rowspan="{row_span}">{name}</td>' if idx == 0 else ''}
                    <td style="padding: 8px 12px; border: 1px solid #dee2e6;"><code>{f}</code></td>
                    <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{old_val}</td>
                    <td style="padding: 8px 12px; border: 1px solid #dee2e6; {color}">{new_val}</td>
                </tr>
                """
        html += '</table>'

    html += '</div>'
    return html


def format_group_ratio_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    old_ratio = old_price.get('group_ratio', {})
    new_ratio = new_price.get('group_ratio', {})
    diff = group_ratio_compare(old_ratio, new_ratio)
    if not diff:
        return None

    html = f"""
    <div style="font-family: Arial, sans-serif;">
        <p><strong>新增:</strong> {len(diff['added'])} 个 &nbsp;|&nbsp; 
           <strong>移除:</strong> {len(diff['removed'])} 个 &nbsp;|&nbsp; 
           <strong>变更:</strong> {len(diff['changed'])} 个</p>
    """

    if diff['added']:
        html += f'<p><span style="color: #28a745;">新增分组:</span> {", ".join(diff["added"])}</p>'
    if diff['removed']:
        html += f'<p><span style="color: #dc3545;">移除分组:</span> {", ".join(diff["removed"])}</p>'

    if diff['changed']:
        html += """
        <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
            <tr style="background: #343a40; color: white;">
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">分组</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">旧倍率</th>
                <th style="padding: 8px 12px; border: 1px solid #dee2e6; text-align: left;">新倍率</th>
            </tr>
        """
        for item in diff['changed'][:10]:
            color = (
                'color: #28a745;'
                if item['new'] > item['old']
                else 'color: #dc3545;'
                if item['new'] < item['old']
                else ''
            )
            html += f"""
            <tr>
                <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{item['group']}</td>
                <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{item['old']}</td>
                <td style="padding: 8px 12px; border: 1px solid #dee2e6; {color}">{item['new']}</td>
            </tr>
            """
        if len(diff['changed']) > 10:
            html += f'<tr><td colspan="3" style="padding: 8px; text-align: center;">... 及其他 {len(diff["changed"]) - 10} 个分组有变动</td></tr>'
        html += '</table>'

    html += '</div>'
    return html


def format_usable_group_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    old_groups = old_price.get('usable_group', {})
    new_groups = new_price.get('usable_group', {})
    diff = usable_group_keys_compare(old_groups, new_groups)
    if not diff:
        return None

    html = f"""
    <div style="font-family: Arial, sans-serif;">
        <p><strong>新增:</strong> {len(diff['added'])} 个 &nbsp;|&nbsp; 
           <strong>移除:</strong> {len(diff['removed'])} 个</p>
    """

    if diff['added']:
        html += f'<p><span style="color: #28a745;">新增分组:</span> {", ".join(diff["added"])}</p>'
    if diff['removed']:
        html += f'<p><span style="color: #dc3545;">移除分组:</span> {", ".join(diff["removed"])}</p>'

    html += '</div>'
    return html


def data_compare(
    old_price: Dict[str, Any],
    new_price: Dict[str, Any],
    compare_keys: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    if compare_keys is None:
        compare_keys = PRICE_RELATED_KEYS

    old_data = old_price.get('data', [])
    new_data = new_price.get('data', [])

    old_map = {item.get('model_name'): item for item in old_data}
    new_map = {item.get('model_name'): item for item in new_data}

    old_names = set(old_map.keys())
    new_names = set(new_map.keys())

    added = [new_map[name] for name in (new_names - old_names)]
    removed = [old_map[name] for name in (old_names - new_names)]

    modified = []
    for name in old_names & new_names:
        old_item = old_map[name]
        new_item = new_map[name]

        changed_fields = []
        for key in compare_keys:
            old_val = old_item.get(key)
            new_val = new_item.get(key)

            if key == 'enable_groups':
                old_set = set(old_val) if isinstance(old_val, list) else set()
                new_set = set(new_val) if isinstance(new_val, list) else set()
                if old_set != new_set:
                    changed_fields.append(key)
            else:
                if old_val != new_val:
                    changed_fields.append(key)

        if changed_fields:
            modified.append(
                {
                    'model_name': name,
                    'changed_fields': changed_fields,
                    'old': old_item,
                    'new': new_item,
                }
            )

    if not added and not removed and not modified:
        return None

    return {'added': added, 'removed': removed, 'modified': modified}


def group_ratio_compare(
    old_ratio: Dict[str, float], new_ratio: Dict[str, float]
) -> Optional[Dict[str, Any]]:
    if old_ratio == new_ratio:
        return None

    old_keys = set(old_ratio.keys())
    new_keys = set(new_ratio.keys())

    changed = []
    for key in old_keys & new_keys:
        if old_ratio[key] != new_ratio[key]:
            changed.append(
                {'group': key, 'old': old_ratio[key], 'new': new_ratio[key]}
            )

    return {
        'added': list(new_keys - old_keys),
        'removed': list(old_keys - new_keys),
        'changed': changed,
    }


def usable_group_keys_compare(
    old: Dict[str, str], new: Dict[str, str]
) -> Optional[Dict[str, List[str]]]:
    old_keys = set(old.keys())
    new_keys = set(new.keys())
    if old_keys == new_keys:
        return None
    return {
        'added': list(new_keys - old_keys),
        'removed': list(old_keys - new_keys),
    }
