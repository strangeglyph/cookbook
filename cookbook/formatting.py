from math import floor, log10
import math


def format_num(num: float) -> str:
    """
    Split a measurement into 'humane' fractions:
    - close to .25 -> 1/4
    - close to .33 -> 1/3
    - close to .5  -> 1/2 etc
    :param num:
    :return:
    """
    if num < 0.29:
        return "¼"
    elif num < 0.4:
        return "⅓"
    elif num < 0.6:
        return "½"
    elif num < 0.7:
        return "⅔"
    elif num <= 0.85:
        return "¾"
    elif num <= 1:
        return "1"
    elif num <= 1.85:
        return "1 " + format_num(num - 1)
    elif num <= 2.15:
        return "2"
    elif num <= 2.35:
        return "2 ¼"
    elif num <= 2.65:
        return "2 ½"
    elif num <= 2.85:
        return "2 ¾"
    elif num <= 3.25:
        return "3"
    elif num <= 3.75:
        return "3 ½"
    elif num <= 4.33:
        return "4"
    elif num <= 5:
        return "5"
    else:
        return str(round_approximate(num))


def round_approximate(num: float) -> int:
    num = int(num)
    if num == 0:
        return 0
    return round(num, -floor(log10(abs(num))) + 2)  # round to 3 sig digits


def round_up(num: float) -> int:
    return math.ceil(num)


def format_instr_part(value):
    from .cookbook.recipev2 import Scalar
    if type(value) == Scalar:
        return (f'<span class="scalar">'
                f'<span class="scalar-amt">{format_num(value.amount)}</span>'
                f'<span class="scalar-per-serving">{value.amount_per_serving}</span>'
                f'</span>')
    else:
        return f'<span class="instr-part">{value}</span>'