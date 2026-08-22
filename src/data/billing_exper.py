import copy
import json
import re
from typing import Dict, Any, List

from config import MAX_BASE_PRICE, PRICE_RATIO, MAX_RATIO


class BillingExper:
    """
    解析、生成、比较并自动修正嵌套条件计费表达式。
    """

    def __init__(self, billing_exper: str):
        self.billing_exper_text = (billing_exper or '').strip()
        self._parsed = None
        self._all_vars = set()

    def parse(self) -> dict:
        if self._parsed is None:
            self._parsed = self._parse_expression(self.billing_exper_text)
            self._collect_vars(self._parsed)
            self._fill_missing(self._parsed)
        return self._parsed

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.parse(), indent=indent, ensure_ascii=False)

    def to_flat(self) -> Dict[str, Dict[str, Any]]:
        tree = self.parse()
        result = {}
        current = tree
        while True:
            if 'condition' not in current:
                result['else'] = {
                    'desc': current['desc'],
                    'price': current['price'].copy(),
                }
                break
            cond = current['condition']
            true_part = current['true']
            if 'condition' not in true_part:
                result[cond] = {
                    'desc': true_part['desc'],
                    'price': true_part['price'].copy(),
                }
            else:
                sub_flat = self._flatten_node(true_part)
                for sub_key, sub_val in sub_flat.items():
                    new_key = (
                        cond if sub_key == 'else' else f'{cond} && {sub_key}'
                    )
                    result[new_key] = sub_val
            current = current['false']
        return result

    def evaluate(self, **kwargs) -> Dict[str, Any]:
        tree = self.parse()
        return self._evaluate_node(tree, kwargs)

    def get_all_prices(self) -> List[Dict[str, Any]]:
        tree = self.parse()
        result = []
        self._collect_leaves(tree, result)
        return result

    def to_expression(self) -> str:
        tree = self.parse()
        return self._node_to_expr(tree)

    @staticmethod
    def compare_exprs(upstream: str, station: str) -> bool:
        if not upstream and not station:
            return True
        if not upstream or not station:
            return False
        try:
            up_tree = BillingExper(upstream).parse()
            st_tree = BillingExper(station).parse()
        except Exception:
            # 解析失败，视为不通过
            return False
        return BillingExper._compare_trees(up_tree, st_tree)

    @staticmethod
    def _compare_trees(node_up: dict, node_st: dict) -> bool:
        is_cond_up = 'condition' in node_up
        is_cond_st = 'condition' in node_st
        if is_cond_up != is_cond_st:
            return False
        if is_cond_up:
            if node_up['condition'] != node_st['condition']:
                return False
            return BillingExper._compare_trees(
                node_up['true'], node_st['true']
            ) and BillingExper._compare_trees(
                node_up['false'], node_st['false']
            )
        else:
            return BillingExper._compare_prices(
                node_up['price'], node_st['price']
            )

    @staticmethod
    def _compare_prices(
        up_price: Dict[str, float], st_price: Dict[str, float]
    ) -> bool:
        for var, coeff in up_price.items():
            if coeff == 0:
                continue
            if var not in st_price:
                return False
            if st_price[var] < coeff:
                return False
        return True

    @staticmethod
    def _compare_structures(node1: dict, node2: dict) -> bool:
        """
        递归比较两个节点的结构（不比较价格系数）。
        返回 True 表示条件分支结构和条件字符串完全一致。
        """
        is_cond1 = 'condition' in node1
        is_cond2 = 'condition' in node2
        if is_cond1 != is_cond2:
            return False
        if is_cond1:
            if node1['condition'] != node2['condition']:
                return False
            return BillingExper._compare_structures(
                node1['true'], node2['true']
            ) and BillingExper._compare_structures(
                node1['false'], node2['false']
            )
        else:
            return True

    # ---------- 自动修正站点表达式 ----------
    @staticmethod
    def correct_station_expr(upstream: str, station: str) -> str:
        """
        根据上游表达式自动修正站点表达式，返回修正后的表达式字符串。
        修正规则：
          1. 若 station_val < upstream_val → 修正为 upstream_val * price_ratio
          2. 若 upstream_val > max_base_price 且 station_val > upstream_val * max_ratio
             → 修正为 upstream_val * price_ratio
        若 station 为空、解析失败或结构不一致，则自动生成一个全零价格树（与上游结构一致），再应用上述修正。
        此外，若站点缺失某个上游变量，则补全该变量，系数设为 upstream_val * price_ratio（若为0则仍为0）。
        """
        # 解析上游，若失败则直接返回原站点（或空）
        try:
            up_parser = BillingExper(upstream)
            up_tree = up_parser.parse()
        except Exception:
            return station or ''

        def zero_prices(node):
            if 'condition' in node:
                zero_prices(node['true'])
                zero_prices(node['false'])
            else:
                for var in node['price']:
                    node['price'][var] = 0.0

        if not station:
            st_tree = copy.deepcopy(up_tree)
            zero_prices(st_tree)
        else:
            try:
                st_parser = BillingExper(station)
                st_tree = st_parser.parse()
            except Exception:
                st_tree = copy.deepcopy(up_tree)
                zero_prices(st_tree)

        if not BillingExper._compare_structures(up_tree, st_tree):
            st_tree = copy.deepcopy(up_tree)
            zero_prices(st_tree)

        new_st_tree = copy.deepcopy(st_tree)

        def correct_node(up_node, st_node):
            if 'condition' in up_node:
                correct_node(up_node['true'], st_node['true'])
                correct_node(up_node['false'], st_node['false'])
            else:
                up_price = up_node['price']
                st_price = st_node['price']
                for var, up_val in up_price.items():
                    if up_val != 0 and var not in st_price:
                        st_price[var] = up_val * PRICE_RATIO
                for var, up_val in up_price.items():
                    if up_val == 0:
                        continue
                    st_val = st_price.get(var, 0.0)
                    if st_val < up_val or (
                        up_val > MAX_BASE_PRICE and st_val > up_val * MAX_RATIO
                    ):
                        st_price[var] = up_val * PRICE_RATIO

        correct_node(up_tree, new_st_tree)
        new_parser = BillingExper('')
        new_parser._parsed = new_st_tree
        return new_parser.to_expression()

    def _parse_expression(self, expr: str):
        expr = expr.strip()
        if not expr:
            return {'desc': 'default', 'price': {}}
        outer = self._find_outer_operator(expr)
        if outer is None:
            if expr.startswith('tier('):
                return self._parse_tier(expr)
            else:
                return self._parse_tier(f'tier("default", {expr})')
        cond, true_expr, false_expr = outer
        return {
            'condition': cond,
            'true': self._parse_branch(true_expr),
            'false': self._parse_branch(false_expr),
        }

    def _parse_branch(self, expr: str):
        expr = expr.strip()
        if expr.startswith('tier('):
            return self._parse_tier(expr)
        else:
            return self._parse_expression(expr)

    def _parse_tier(self, expr: str) -> dict:
        pattern = r'tier\s*\(\s*\"([^\"]+)\"\s*,\s*(.*)\s*\)'
        match = re.match(pattern, expr, re.DOTALL)
        if not match:
            raise ValueError(f'无效的 tier 表达式: {expr}')
        desc = match.group(1)
        price_expr = match.group(2)
        price_dict = self._parse_price(price_expr)
        return {'desc': desc, 'price': price_dict}

    def _parse_price(self, price_expr: str) -> dict:
        terms = price_expr.split('+')
        price = {}
        for term in terms:
            term = term.strip()
            if not term:
                continue
            m = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\*\s*([\d.]+)', term)
            if not m:
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', term):
                    var, coeff = term, 1.0
                else:
                    raise ValueError(f'无效的项: {term}')
            else:
                var, coeff = m.group(1), float(m.group(2))
            # 仅当系数不为 0 时存储
            if coeff != 0:
                price[var] = coeff
        return price

    def _find_outer_operator(self, expr: str):
        depth = 0
        q_pos = -1
        for i, ch in enumerate(expr):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == '?' and depth == 0:
                q_pos = i
                break
        if q_pos == -1:
            return None

        depth = 0
        colon_pos = -1
        for i in range(q_pos + 1, len(expr)):
            ch = expr[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ':' and depth == 0:
                colon_pos = i
                break
        if colon_pos == -1:
            raise ValueError("找不到匹配的 ':'")
        cond = expr[:q_pos].strip()
        true_expr = expr[q_pos + 1 : colon_pos].strip()
        false_expr = expr[colon_pos + 1 :].strip()
        return cond, true_expr, false_expr

    def _collect_vars(self, node: dict):
        if 'condition' in node:
            self._collect_vars(node['true'])
            self._collect_vars(node['false'])
        else:
            self._all_vars.update(node['price'].keys())

    def _fill_missing(self, node: dict):
        if 'condition' in node:
            self._fill_missing(node['true'])
            self._fill_missing(node['false'])
        else:
            price = node['price']
            for var in self._all_vars:
                if var not in price:
                    price[var] = 0.0

    def _flatten_node(self, node: dict) -> dict:
        result = {}
        current = node
        while True:
            if 'condition' not in current:
                result['else'] = {
                    'desc': current['desc'],
                    'price': current['price'].copy(),
                }
                break
            cond = current['condition']
            true_part = current['true']
            if 'condition' not in true_part:
                result[cond] = {
                    'desc': true_part['desc'],
                    'price': true_part['price'].copy(),
                }
            else:
                sub = self._flatten_node(true_part)
                for k, v in sub.items():
                    result[f'{cond} && {k}'] = v if k != 'else' else v
            current = current['false']
        return result

    def _evaluate_node(self, node: dict, kwargs: dict) -> dict:
        if 'condition' not in node:
            return node
        try:
            result = eval(node['condition'], {}, kwargs)
        except Exception as e:
            raise ValueError(f'条件评估失败: {node["condition"]}, 错误: {e}')
        if result:
            return self._evaluate_node(node['true'], kwargs)
        else:
            return self._evaluate_node(node['false'], kwargs)

    def _collect_leaves(self, node: dict, result: list):
        if 'condition' in node:
            self._collect_leaves(node['true'], result)
            self._collect_leaves(node['false'], result)
        else:
            result.append(
                {'desc': node['desc'], 'price': node['price'].copy()}
            )

    def _node_to_expr(self, node: dict) -> str:
        if 'condition' in node:
            cond = node['condition']
            true_expr = self._node_to_expr(node['true'])
            false_expr = self._node_to_expr(node['false'])
            return f'{cond} ? {true_expr} : {false_expr}'
        else:
            desc = node['desc']
            price_expr = self._price_to_expr(node['price'])
            return f'tier("{desc}", {price_expr})'

    def _price_to_expr(self, price: dict) -> str:
        """
        将价格字典转换为表达式，跳过系数为0的项。
        变量顺序固定为：p, c, cr, cc, cc1h, img, img_o, ai, ao
        其余未列出的变量按字母顺序追加。
        """
        # 期望的顺序
        order = ['p', 'c', 'cr', 'cc', 'cc1h', 'img', 'img_o', 'ai', 'ao']
        all_vars = set(price.keys())
        ordered_vars = []
        for var in order:
            if var in all_vars:
                ordered_vars.append(var)
                all_vars.remove(var)
        ordered_vars.extend(sorted(all_vars))

        items = []
        for var in ordered_vars:
            coeff = price[var]
            if coeff == 0:
                continue
            if isinstance(coeff, float) and coeff.is_integer():
                coeff_str = str(int(coeff))
            else:
                # 使用 12 位有效数字，自动去除多余零和浮点误差
                coeff_str = f'{coeff:.12g}'
            items.append(f'{var} * {coeff_str}')
        return ' + '.join(items)


if __name__ == '__main__':
    upstream_expr = (
        'len > 20 ? tier("base", p * 1 + c * 1 + cr * 0.999996 + cc * 1) : '
        'len < 20000 ? tier("tier_2", p * 1 + c * 1 + cr * 1) : '
        'tier("tier_3", p * 1 + c * 1)'
    )

    # 测试空表达式和裸价格
    empty_expr = ''
    bare_expr = 'p * 0 + c * 0'

    print('=== 空表达式解析 ===')
    parser_empty = BillingExper(empty_expr)
    print(parser_empty.to_expression())  # 输出 tier("default", )

    print('\n=== 裸价格表达式解析 ===')
    parser_bare = BillingExper(bare_expr)
    print(parser_bare.to_expression())  # 输出 tier("default", p * 0 + c * 0)

    print('\n=== 比较空表达式与上游 ===')
    print(BillingExper.compare_exprs(upstream_expr, empty_expr))  # False

    print('\n=== 比较裸价格与上游 ===')
    print(BillingExper.compare_exprs(upstream_expr, bare_expr))  # False

    # 修正裸价格（自动变成零树后修正）
    corrected = BillingExper.correct_station_expr(upstream_expr, bare_expr)
    print('\n=== 修正后的裸价格 ===')
    print(corrected)
