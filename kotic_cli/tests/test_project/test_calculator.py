# test_calculator.py
import pytest
from .calculator import add, subtract, multiply, divide

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0

def test_subtract():
    assert subtract(5, 2) == 3
    assert subtract(10, 5) == 5
    assert subtract(-1, -1) == 0 # Этот тест упадет из-за бага

def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(-1, 5) == -5
    assert multiply(0, 100) == 0

def test_divide():
    assert divide(10, 2) == 5.0
    assert divide(-10, 2) == -5.0
    with pytest.raises(ValueError):
        divide(10, 0)
