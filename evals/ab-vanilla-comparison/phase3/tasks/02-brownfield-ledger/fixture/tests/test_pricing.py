"""기본 주문의 가격 계산 예제."""

import unittest
from ledger import total


class PricingTests(unittest.TestCase):
    def test_percent_coupon(self):
        self.assertEqual(total({"items": [{"qty": 2, "unit_price": 50}],
                                "coupon": {"type": "percent", "value": 10}}), 90.0)

    def test_tax_only(self):
        self.assertEqual(total({"items": [{"qty": 1, "unit_price": 100}],
                                "tax_rate_pct": 8}), 108.0)

    def test_without_coupon_or_tax(self):
        self.assertEqual(total({"items": [{"qty": 3, "unit_price": 10}]}), 30.0)
