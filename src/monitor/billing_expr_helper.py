import re
from typing import Dict, List, Tuple


# ------- 辅助函数 -------
def _tokenize(expr: str) -> List[str]:
    """将表达式拆分为 token 列表"""
    pattern = r'[a-zA-Z_][a-zA-Z0-9_]*|"[^"]*"|\d+\.?\d*|<=|>=|==|!=|[+\-*/()?,:]|[<>]'
    return re.findall(pattern, expr)


def _parse_billing_expr(tokens: List[str], pos: int = 0) -> Tuple[Dict, int]:
    """
    递归解析，返回 (ast, new_pos)
    ast 结构：
        {'type': 'conditional', 'cond': str, 'true': ast, 'false': ast}
        {'type': 'tier', 'label': str, 'expr': ast}
        {'type': 'binary', 'op': str, 'left': ast, 'right': ast}
        {'type': 'var', 'name': str}
        {'type': 'number', 'value': float}
        {'type': 'string', 'value': str}   # 仅用于 tier 标签
    """
    token = tokens[pos]
    if token == 'tier':
        pos += 1
        assert tokens[pos] == '('
        pos += 1
        label_token = tokens[pos]
        assert label_token.startswith('"')
        label = label_token[1:-1]
        pos += 1
        assert tokens[pos] == ','
        pos += 1
        expr_ast, pos = _parse_expr(tokens, pos)
        assert tokens[pos] == ')'
        pos += 1
        return {'type': 'tier', 'label': label, 'expr': expr_ast}, pos

    elif token == '(':
        pos += 1
        ast, pos = _parse_expr(tokens, pos)
        assert tokens[pos] == ')'
        pos += 1
        return ast, pos

    elif token.isidentifier() or token.replace('.', '').isdigit():
        pos += 1
        if token.replace('.', '').isdigit():
            return {'type': 'number', 'value': float(token)}, pos
        else:
            return {'type': 'var', 'name': token}, pos

    elif token.startswith('"'):
        pos += 1
        return {'type': 'string', 'value': token[1:-1]}, pos

    else:
        # 二元运算符或比较运算符：我们需要左操作数已解析，但这里 token 是运算符，
        # 所以不应当直接到达这里，应该由 parse_expr 处理
        raise SyntaxError(f'Unexpected token: {token}')


def _parse_expr(tokens: List[str], pos: int) -> Tuple[Dict, int]:
    """解析表达式（可能包含 ? : 或二元运算）"""
    # 先解析一个主表达式
    left, pos = _parse_primary(tokens, pos)

    # 如果遇到 ? ，则处理三元条件
    if pos < len(tokens) and tokens[pos] == '?':
        pos += 1
        true_ast, pos = _parse_expr(tokens, pos)
        assert tokens[pos] == ':'
        pos += 1
        false_ast, pos = _parse_expr(tokens, pos)
        # 将条件部分提取为字符串（从 left 中提取）
        # 这里 left 可能是一个比较表达式，我们将其转换为字符串
        cond_str = _ast_to_str(left)  # 实现一个简单的 to_str 函数
        return {
            'type': 'conditional',
            'cond': cond_str,
            'true': true_ast,
            'false': false_ast,
        }, pos

    # 如果遇到运算符，继续解析（此处仅处理二元运算符）
    while pos < len(tokens) and tokens[pos] in (
        '+',
        '-',
        '*',
        '/',
        '<=',
        '>=',
        '<',
        '>',
        '==',
        '!=',
    ):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_primary(tokens, pos)
        left = {'type': 'binary', 'op': op, 'left': left, 'right': right}
    return left, pos


def _parse_primary(tokens: List[str], pos: int) -> Tuple[Dict, int]:
    # 处理括号、tier、标识符、数字、字符串
    token = tokens[pos]
    if token == '(':
        pos += 1
        ast, pos = _parse_expr(tokens, pos)
        assert tokens[pos] == ')'
        pos += 1
        return ast, pos
    elif token == 'tier':
        return _parse_billing_expr(tokens, pos)
    elif token.startswith('"'):
        pos += 1
        return {'type': 'string', 'value': token[1:-1]}, pos
    elif token.isidentifier():
        pos += 1
        return {'type': 'var', 'name': token}, pos
    elif token.replace('.', '').isdigit():
        pos += 1
        return {'type': 'number', 'value': float(token)}, pos
    else:
        raise SyntaxError(f'Unexpected token: {token}')


def _ast_to_str(ast: Dict) -> str:
    """将 AST 节点转回字符串（仅用于提取条件）"""
    if ast['type'] == 'var':
        return ast['name']
    elif ast['type'] == 'number':
        return str(ast['value'])
    elif ast['type'] == 'binary':
        return f'{_ast_to_str(ast["left"])} {ast["op"]} {_ast_to_str(ast["right"])}'
    elif ast['type'] == 'string':
        return f'"{ast["value"]}"'
    elif ast['type'] == 'tier':
        return f'tier("{ast["label"]}", {_ast_to_str(ast["expr"])})'
    elif ast['type'] == 'conditional':
        return f'{_ast_to_str(ast["cond"])} ? {_ast_to_str(ast["true"])} : {_ast_to_str(ast["false"])}'
    else:
        return ''


def _normalize_label(label: str) -> str:
    """将 tier 标签中的数字替换为 "?"""
    return re.sub(r'\d+\.?\d*', '?', label)


def _extract_coeffs(ast: Dict) -> Dict[str, float]:
    """
    从 AST 中提取变量系数（仅处理加减乘，忽略除）
    例如 p * 0.9 + c * 5.4 -> {'p': 0.9, 'c': 5.4}
    """
    if ast['type'] == 'var':
        return {ast['name']: 1.0}
    if ast['type'] == 'number':
        return {}  # 常数项，忽略
    if ast['type'] == 'binary':
        left = _extract_coeffs(ast['left'])
        right = _extract_coeffs(ast['right'])
        op = ast['op']
        if op == '+':
            # 合并系数
            result = left.copy()
            for k, v in right.items():
                result[k] = result.get(k, 0) + v
            return result
        elif op == '-':
            result = left.copy()
            for k, v in right.items():
                result[k] = result.get(k, 0) - v
            return result
        elif op == '*':
            # 处理乘法：常数 * 变量 或 变量 * 常数
            # 判断左右哪边是常数
            if (
                ast['left']['type'] == 'number'
                and ast['right']['type'] == 'var'
            ):
                const = ast['left']['value']
                return {ast['right']['name']: const}
            elif (
                ast['right']['type'] == 'number'
                and ast['left']['type'] == 'var'
            ):
                const = ast['right']['value']
                return {ast['left']['name']: const}
            elif (
                ast['left']['type'] == 'number'
                and ast['right']['type'] == 'binary'
            ):
                # 如 2 * (p * 0.5) -> 递归
                sub = _extract_coeffs(ast['right'])
                const = ast['left']['value']
                return {k: v * const for k, v in sub.items()}
            elif (
                ast['right']['type'] == 'number'
                and ast['left']['type'] == 'binary'
            ):
                sub = _extract_coeffs(ast['left'])
                const = ast['right']['value']
                return {k: v * const for k, v in sub.items()}
            else:
                # 变量相乘，如 p * c，不常见，忽略
                return {}
        else:
            # 除法、比较等不处理
            return {}
    return {}


def _compare_ast(up_ast: Dict, st_ast: Dict) -> bool:
    """
    递归比较两个 AST，按规则：
      - conditional: 条件字符串完全一致，比较 true 和 false
      - tier: label 忽略数字，比较 expr
      - binary: 比较运算符，递归比较左右
      - var: 变量名相等
      - number: 要求 st >= up
    """
    if up_ast['type'] != st_ast['type']:
        return False
    if up_ast['type'] == 'conditional':
        if up_ast['cond'] != st_ast['cond']:
            return False
        return _compare_ast(up_ast['true'], st_ast['true']) and _compare_ast(
            up_ast['false'], st_ast['false']
        )
    if up_ast['type'] == 'tier':
        if _normalize_label(up_ast['label']) != _normalize_label(
            st_ast['label']
        ):
            return False
        return _compare_ast(up_ast['expr'], st_ast['expr'])
    if up_ast['type'] == 'binary':
        if up_ast['op'] != st_ast['op']:
            return False
        return _compare_ast(up_ast['left'], st_ast['left']) and _compare_ast(
            up_ast['right'], st_ast['right']
        )
    if up_ast['type'] == 'var':
        return up_ast['name'] == st_ast['name']
    if up_ast['type'] == 'number':
        return st_ast['value'] >= up_ast['value']
    if up_ast['type'] == 'string':
        return up_ast['value'] == st_ast['value']
    return True
