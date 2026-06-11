// 주문 금액별 할인율 SSOT.
// 정책(README·테스트가 진실): 100 이상 10%, 500 이상 20% — 경계 포함.
function discountRate(amount) {
  if (amount > 500) return 0.2;
  if (amount > 100) return 0.1;
  return 0;
}

module.exports = { discountRate };
