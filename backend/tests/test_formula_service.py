import pandas as pd
import pytest
from fastapi import HTTPException

from app.services import formula_service


# ---------------------------------------------------------------------------
# Tokenizer tests
# ---------------------------------------------------------------------------


def test_tokenize_simple_columns():
    tokens = formula_service._tokenize("quantity * unit_price")
    assert tokens == ["quantity", "*", "unit_price"]


def test_tokenize_with_numbers():
    tokens = formula_service._tokenize("col1 * 1.1")
    assert tokens == ["col1", "*", "1.1"]


def test_tokenize_with_parentheses():
    tokens = formula_service._tokenize("(col1 + col2) * 0.1")
    assert tokens == ["(", "col1", "+", "col2", ")", "*", "0.1"]


def test_tokenize_empty():
    tokens = formula_service._tokenize("")
    assert tokens == []


def test_tokenize_whitespace():
    tokens = formula_service._tokenize("  col1   *   col2  ")
    assert tokens == ["col1", "*", "col2"]


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def test_parse_simple_multiply():
    ast = formula_service.parse_formula("quantity * unit_price", {"quantity", "unit_price"})
    assert ast["op"] == "*"
    assert ast["left"]["type"] == "column"
    assert ast["left"]["name"] == "quantity"
    assert ast["right"]["type"] == "column"
    assert ast["right"]["name"] == "unit_price"


def test_parse_subtract():
    ast = formula_service.parse_formula("unit_price - discount", {"unit_price", "discount"})
    assert ast["op"] == "-"


def test_parse_unknown_column():
    with pytest.raises(formula_service.FormulaError) as exc:
        formula_service.parse_formula("unknown_col * 1.1", {"col1", "col2"})
    assert "Unknown column" in str(exc.value)


def test_parse_empty_formula():
    with pytest.raises(formula_service.FormulaError) as exc:
        formula_service.parse_formula("", {"col1"})
    assert "empty" in str(exc.value).lower()


def test_parse_unsupported_char():
    with pytest.raises(formula_service.FormulaError) as exc:
        formula_service.parse_formula("col1 @ col2", {"col1", "col2"})
    assert "Unexpected character" in str(exc.value)


def test_parse_parentheses():
    ast = formula_service.parse_formula("(col1 + col2) * 0.1", {"col1", "col2"})
    assert ast is not None


# ---------------------------------------------------------------------------
# apply_formula tests
# ---------------------------------------------------------------------------


def test_apply_multiply_two_columns():
    df = pd.DataFrame({"quantity": [2, 3, 4], "unit_price": [10.0, 20.0, 30.0]})
    result = formula_service.apply_formula(df, "quantity * unit_price")
    assert list(result) == [20.0, 60.0, 120.0]


def test_apply_subtract_discount():
    df = pd.DataFrame({"unit_price": [100.0, 200.0], "discount": [10.0, 20.0]})
    result = formula_service.apply_formula(df, "unit_price - discount")
    assert list(result) == [90.0, 180.0]


def test_apply_with_number_literal():
    df = pd.DataFrame({"unit_price": [100.0, 200.0]})
    result = formula_service.apply_formula(df, "unit_price * 1.1")
    assert abs(result[0] - 110.0) < 0.001
    assert abs(result[1] - 220.0) < 0.001


def test_apply_with_parentheses():
    df = pd.DataFrame({"col1": [1.0, 2.0], "col2": [3.0, 4.0]})
    result = formula_service.apply_formula(df, "(col1 + col2) * 0.1")
    assert abs(result[0] - 0.4) < 0.001
    assert abs(result[1] - 0.6) < 0.001


def test_apply_unknown_column():
    df = pd.DataFrame({"col1": [1, 2]})
    with pytest.raises(HTTPException) as exc:
        formula_service.apply_formula(df, "col1 * unknown_col")
    assert exc.value.status_code == 400
    assert "Unknown column" in exc.value.detail


def test_apply_empty_formula():
    df = pd.DataFrame({"col1": [1, 2]})
    with pytest.raises(HTTPException) as exc:
        formula_service.apply_formula(df, "")
    assert exc.value.status_code == 400


def test_apply_unsupported_character():
    df = pd.DataFrame({"col1": [1, 2]})
    with pytest.raises(HTTPException) as exc:
        formula_service.apply_formula(df, "col1 @ col2")
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Complex formula tests
# ---------------------------------------------------------------------------


def test_apply_net_revenue_formula():
    """quantity × unit_price = net revenue"""
    df = pd.DataFrame({
        "quantity": [5, 10, 3],
        "unit_price": [100.0, 50.0, 200.0],
    })
    result = formula_service.apply_formula(df, "quantity * unit_price")
    assert list(result) == [500.0, 500.0, 600.0]


def test_apply_discounted_price_formula():
    """unit_price - discount = discounted price"""
    df = pd.DataFrame({
        "unit_price": [100.0, 200.0, 300.0],
        "discount": [10.0, 20.0, 30.0],
    })
    result = formula_service.apply_formula(df, "unit_price - discount")
    assert list(result) == [90.0, 180.0, 270.0]


def test_apply_tax_formula():
    """quantity × unit_price × 0.1 = tax"""
    df = pd.DataFrame({
        "quantity": [2, 5],
        "unit_price": [100.0, 200.0],
    })
    result = formula_service.apply_formula(df, "quantity * unit_price * 0.1")
    assert list(result) == [20.0, 100.0]