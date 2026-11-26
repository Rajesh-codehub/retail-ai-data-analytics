"""Safe formula evaluation service.

Supports a limited set of formulas without using eval():
- multiply two columns: col1 * col2
- subtract a discount: col1 - discount

All operations are column-safe and validate column references before execution.
"""

import re
from typing import Any, Dict, List
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, status


# ---------------------------------------------------------------------------
# Safe formula parser
# ---------------------------------------------------------------------------

class FormulaError(Exception):
    """Raised when a formula is invalid or references unknown columns."""
    pass


def _tokenize(formula: str) -> List[str]:
    """Tokenize a formula string into column names, operators, and numbers.

    Supports:
    - Column names: [a-zA-Z_][a-zA-Z0-9_]*
    - Numbers: digits with optional decimal
    - Operators: *, -, +, /, (, )
    - Whitespace is ignored
    """
    tokens = []
    i = 0
    while i < len(formula):
        ch = formula[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit() or ch == '.':
            # Number
            start = i
            while i < len(formula) and (formula[i].isdigit() or formula[i] == '.'):
                i += 1
            tokens.append(formula[start:i])
            continue
        if ch.isalpha() or ch == '_':
            # Column name or function
            start = i
            while i < len(formula) and (formula[i].isalnum() or formula[i] == '_'):
                i += 1
            tokens.append(formula[start:i])
            continue
        if ch in '*+-()/':
            tokens.append(ch)
            i += 1
            continue
        raise FormulaError(f"Unexpected character '{ch}' in formula")
    return tokens


def _parse_expression(tokens: List[str], pos: int, available_columns: set) -> tuple:
    """Parse an expression: term (('+' | '-') term)*"""
    left, pos = _parse_term(tokens, pos, available_columns)
    while pos < len(tokens) and tokens[pos] in ('+', '-'):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_term(tokens, pos, available_columns)
        left = {'op': op, 'left': left, 'right': right}
    return left, pos


def _parse_term(tokens: List[str], pos: int, available_columns: set) -> tuple:
    """Parse a term: factor (('*' | '/') factor)*"""
    left, pos = _parse_factor(tokens, pos, available_columns)
    while pos < len(tokens) and tokens[pos] in ('*', '/'):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_factor(tokens, pos, available_columns)
        left = {'op': op, 'left': left, 'right': right}
    return left, pos


def _parse_factor(tokens: List[str], pos: int, available_columns: set) -> tuple:
    """Parse a factor: number | column | '(' expression ')'"""
    if pos >= len(tokens):
        raise FormulaError("Unexpected end of formula")

    token = tokens[pos]

    if token == '(':
        pos += 1
        node, pos = _parse_expression(tokens, pos, available_columns)
        if pos >= len(tokens) or tokens[pos] != ')':
            raise FormulaError("Missing closing parenthesis")
        pos += 1
        return node, pos

    if token.replace('.', '', 1).isdigit():
        # Number literal
        return {'type': 'number', 'value': float(token)}, pos + 1

    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', token):
        # Column reference
        if token not in available_columns:
            raise FormulaError(f"Unknown column '{token}'")
        return {'type': 'column', 'name': token}, pos + 1

    raise FormulaError(f"Unexpected token '{token}' in formula")


def parse_formula(formula: str, available_columns: set) -> dict:
    """Parse a formula string into an AST.

    Raises FormulaError if the formula is invalid or references unknown columns.
    """
    if not formula or not formula.strip():
        raise FormulaError("Formula cannot be empty")

    tokens = _tokenize(formula)
    if not tokens:
        raise FormulaError("Formula cannot be empty")

    ast, pos = _parse_expression(tokens, 0, available_columns)
    if pos < len(tokens):
        raise FormulaError(f"Unexpected token '{tokens[pos]}' at end of formula")

    return ast


def _evaluate_node(node: dict, df: pd.DataFrame) -> Any:
    """Evaluate an AST node against a DataFrame, returning a Series."""
    if 'op' in node:
        op = node['op']
        left = _evaluate_node(node['left'], df)
        right = _evaluate_node(node['right'], df)

        if op == '+':
            return left + right
        if op == '-':
            return left - right
        if op == '*':
            return left * right
        if op == '/':
            return left / right

        raise FormulaError(f"Unsupported operator '{op}'")

    if node['type'] == 'number':
        return pd.Series([node['value']] * len(df), index=df.index)
    if node['type'] == 'column':
        return df[node['name']]

    raise FormulaError(f"Unknown node type '{node.get('type', 'unknown')}'")


def apply_formula(df: pd.DataFrame, formula: str) -> pd.Series:
    """Apply a formula to a DataFrame and return a Series result.

    Raises HTTPException if the formula is invalid or references unknown columns.
    """
    available_columns = set(df.columns)
    try:
        ast = parse_formula(formula, available_columns)
        return _evaluate_node(ast, df)
    except FormulaError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Formula evaluation failed: {exc}",
        )