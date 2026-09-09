"""JSON 주문 파일을 받는 명령행 진입점."""

import json
import sys
from decimal import DecimalException
from .pricing import total


def main():
    if len(sys.argv) != 2:
        print("사용법: python -m ledger <order.json>", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as source:
            order = json.load(source)
        amount = total(order)
        print(f"{amount:.2f}")
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError, DecimalException) as error:
        print(f"입력 오류: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
