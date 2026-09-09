"""가격 계산과 주문 입력 검증."""

from decimal import Decimal


def _number(value, name):
    """JSON 숫자만 허용하며 비유한 수와 음수를 거부한다."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name}: 숫자가 필요합니다")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError(f"{name}: 유한한 0 이상 숫자가 필요합니다")
    return number


def validate(order):
    """잘못된 주문은 계산 전에 ValueError로 알린다."""
    if not isinstance(order, dict) or not isinstance(order.get("items"), list):
        raise ValueError("items: 품목 배열이 필요합니다")
    for item in order["items"]:
        if not isinstance(item, dict):
            raise ValueError("품목은 객체여야 합니다")
        qty = item.get("qty")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            raise ValueError("qty: 1 이상 정수가 필요합니다")
        price = _number(item.get("unit_price"), "unit_price")
        digits = "".join(map(str, price.as_tuple().digits))
        places = max(0, -price.as_tuple().exponent - (len(digits) - len(digits.rstrip("0"))))
        if price and places > 4:
            raise ValueError("unit_price: 소수 넷째 자리까지만 허용합니다")
    coupon = order.get("coupon")
    if coupon is not None:
        if not isinstance(coupon, dict) or coupon.get("type") not in ("fixed", "percent"):
            raise ValueError("coupon.type: fixed 또는 percent가 필요합니다")
        value = _number(coupon.get("value"), "coupon.value")
        if coupon["type"] == "percent" and value > 100:
            raise ValueError("percent: 0부터 100까지 허용합니다")
    _number(order.get("tax_rate_pct", 0), "tax_rate_pct")


def subtotal(items):
    """품목의 수량과 단가로 소계를 구한다."""
    amount = Decimal(str(sum(item["qty"] * float(item["unit_price"]) for item in items)))
    return round(amount, 2)


def total(order):
    """주문의 최종 총액을 구한다."""
    validate(order)
    # 조정 항목이 없는 주문은 라인 합계에서 바로 총액을 구한다.
    if not order.get("coupon") and not order.get("tax_rate_pct", 0):
        return round(sum(item["qty"] * float(item["unit_price"]) for item in order["items"]), 2)
    base = float(subtotal(order["items"]))
    amount = base * (1 + float(order.get("tax_rate_pct", 0)) / 100)
    coupon = order.get("coupon")
    if coupon:
        value = float(coupon["value"])
        if coupon["type"] == "percent":
            amount *= 1 - value / 100
        else:
            amount = 0.0 if value >= base else max(0.0, amount - value)
    return round(amount, 2)
