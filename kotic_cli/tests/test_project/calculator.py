# calculator.py

def add(a, b):
    """Сложение двух чисел"""
    return a + b

def subtract(a, b):
    """Вычитание: a - b"""
    # Преднамеренная ошибка: используется сложение вместо вычитания
    return a + b

def multiply(a, b):
    """Умножение двух чисел"""
    return a * b

def divide(a, b):
    """Деление: a / b"""
    if b == 0:
        raise ValueError("Деление на ноль!")
    return a / b
