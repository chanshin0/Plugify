// mock DB — 호출당 지연으로 실DB 왕복을 흉내낸다.
const ITEMS = Array.from({ length: 10000 }, (_, i) => ({
  id: i,
  title: `상품 ${i} ${i % 7 === 0 ? "한정판" : "일반"}`,
  categoryId: i % 5,
  description: "설명 ".repeat(40),
}));

const USERS = Array.from({ length: 200 }, (_, i) => ({ id: i, name: `user-${i}` }));
const ORDERS = Array.from({ length: 50 }, (_, i) => ({ id: i, userId: i % 200, itemId: i * 3 }));

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

module.exports = {
  async listOrders() { await delay(10); return ORDERS; },
  async getUser(id) { await delay(15); return USERS.find((u) => u.id === id) ?? null; },
  async allItems() { await delay(30); return ITEMS; },
};
