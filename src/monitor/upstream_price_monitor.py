import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from config import PRICE_RELATED_KEYS
from monitor.upstream import get_upstream_price
from remind.sender import send_email
from store.json import get_json, save_json

logger = logging.getLogger(__name__)


async def monitor_upstream_price():
    try:
        old_price = get_json('upstream_price')
        if not old_price:
            get_upstream_price()
            logger.info('首次运行，已保存价格快照，跳过比较')
            return

        new_price = get_upstream_price()
        if not new_price:
            logger.warning('上游价格获取失败')
            return

        logger.info(
            '上游价格获取成功，版本: %s',
            new_price.get('pricing_version', '未知'),
        )

        report = build_change_report(old_price, new_price)

        save_json(new_price, 'upstream_price')

        if report is None:
            logger.info('价格无变化')
        else:
            logger.info('检测到价格变动，发送邮件通知')
            await send_email(report)

    except Exception as e:
        logger.error('监控任务执行异常: %s', e, exc_info=True)


def build_change_report(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    old_version = old_price.get('pricing_version', '未知')
    new_version = new_price.get('pricing_version', '未知')

    if old_version == new_version:
        return None

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
            reports.append(f'【{name}】\n{result}')

    if not reports:
        return None

    header = build_report_header(old_version, new_version)
    body = '\n\n'.join(reports)
    return f'{header}\n\n{body}'


def build_report_header(old_version: str, new_version: str) -> str:
    return (
        f'📊 价格变动报告 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
        f'旧版本: {old_version}\n'
        f'新版本: {new_version}\n'
        f'{"=" * 25}'
    )


def format_auto_groups_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    """格式化自动分组变动"""
    old_list = old_price.get('auto_groups', [])
    new_list = new_price.get('auto_groups', [])

    if old_list == new_list:
        return None

    lines = []
    len1, len2 = len(old_list), len(new_list)

    # 逐位比较
    for i in range(min(len1, len2)):
        if old_list[i] != new_list[i]:
            lines.append(f"  索引 {i}: '{old_list[i]}' → '{new_list[i]}'")

    # 长度差异
    if len1 > len2:
        lines.append(f'  被移除: {old_list[len2:]}')
    elif len2 > len1:
        lines.append(f'  新增: {new_list[len1:]}')

    return '\n'.join(lines) if lines else None


def format_data_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    diff = data_compare(old_price, new_price)
    if not diff:
        return None

    added = diff.get('added', [])
    removed = diff.get('removed', [])
    modified = diff.get('modified', [])

    lines = [
        f'新增: {len(added)} 个',
        f'移除: {len(removed)} 个',
        f'修改: {len(modified)} 个',
    ]

    if removed:
        names = [item.get('model_name', '未知') for item in removed]
        lines.append(f'移除的模型: {", ".join(names)}')

    if added:
        brief = []
        for item in added[:10]:
            name = item.get('model_name', '未知')
            vendor = item.get('vendor_id', '?')
            ratio = item.get('model_ratio', '?')
            comp = item.get('completion_ratio', '?')
            brief.append(
                f'  {name} (vendor={vendor}, ratio={ratio}, comp={comp})'
            )
        if len(added) > 10:
            brief.append(f'  ... 及其他 {len(added) - 10} 个')
        lines.append('新增模型:\n' + '\n'.join(brief))

    if modified:
        lines.append('修改:')
        for m in modified[:5]:
            name = m.get('model_name', '未知')
            fields = m.get('changed_fields', [])
            old_item = m.get('old', {})
            new_item = m.get('new', {})
            changes = []
            for f in fields:
                old_val = old_item.get(f, '无')
                new_val = new_item.get(f, '无')
                changes.append(f'{f}: {old_val} → {new_val}')
            lines.append(f'  {name}: ' + '; '.join(changes))
        if len(modified) > 5:
            lines.append(f'  ... 及其他 {len(modified) - 5} 个')

    return '\n'.join(lines)


def format_group_ratio_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    old_ratio = old_price.get('group_ratio', {})
    new_ratio = new_price.get('group_ratio', {})
    diff = group_ratio_compare(old_ratio, new_ratio)
    if not diff:
        return None

    lines = [
        f'新增: {len(diff["added"])} 个',
        f'移除: {len(diff["removed"])} 个',
        f'变更: {len(diff["changed"])} 个',
    ]

    if diff['added']:
        lines.append(f'  新增: {", ".join(diff["added"])}')
    if diff['removed']:
        lines.append(f'  移除: {", ".join(diff["removed"])}')
    for item in diff['changed'][:5]:
        lines.append(f'  {item["group"]}: {item["old"]} → {item["new"]}')
    if len(diff['changed']) > 5:
        lines.append(f'  ... 及其他 {len(diff["changed"]) - 5} 个')

    return '\n'.join(lines)


def format_usable_group_diff(
    old_price: Dict[str, Any], new_price: Dict[str, Any]
) -> Optional[str]:
    old_groups = old_price.get('usable_group', {})
    new_groups = new_price.get('usable_group', {})
    diff = usable_group_keys_compare(old_groups, new_groups)
    if not diff:
        return None

    lines = [
        f'新增: {len(diff["added"])} 个',
        f'移除: {len(diff["removed"])} 个',
    ]
    if diff['added']:
        lines.append(f'  新增: {", ".join(diff["added"])}')
    if diff['removed']:
        lines.append(f'  移除: {", ".join(diff["removed"])}')

    return '\n'.join(lines)


def data_compare(
    old_price: Dict[str, Any],
    new_price: Dict[str, Any],
    compare_keys: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    比较新旧模型数据列表，**仅比较与价格相关的字段**。
    其中 enable_groups 字段比较时忽略顺序（视为集合）。
    返回: {"added": [...], "removed": [...], "modified": [...]} 或 None
    """
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

            # 针对 enable_groups 进行集合比较（忽略顺序）
            if key == 'enable_groups':
                # 确保值为列表，若为 None 则当作空列表
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
