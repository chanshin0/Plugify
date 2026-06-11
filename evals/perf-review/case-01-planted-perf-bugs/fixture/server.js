// 미니 커머스 API — node 내장만 사용. 핫패스 = GET / (홈), GET /orders, GET /search
const http = require("http");
const fs = require("fs");
const path = require("path");
const db = require("./db");

function renderHome() {
  const tpl = fs.readFileSync(path.join(__dirname, "template.html"), "utf8");
  return tpl.replace("{{now}}", new Date().toISOString());
}

async function ordersWithUsers() {
  const orders = await db.listOrders();
  const out = [];
  for (const o of orders) {
    const user = await db.getUser(o.userId);
    out.push({ ...o, userName: user ? user.name : null });
  }
  return out;
}

// 카테고리는 5개 고정 상수 — 선형 탐색이어도 비용 무시 가능(Map/인덱스 불필요, 의도된 단순함).
const CATEGORIES = [
  { id: 0, label: "디지털" },
  { id: 1, label: "패션" },
  { id: 2, label: "리빙" },
  { id: 3, label: "푸드" },
  { id: 4, label: "취미" },
];
const categoryLabel = (id) => CATEGORIES.find((c) => c.id === id)?.label ?? "기타";

async function search(q) {
  const items = await db.allItems();
  const hits = items.filter((i) => i.title.includes(q));
  return hits.map((i) => ({ ...i, category: categoryLabel(i.categoryId) }));
}

http
  .createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    try {
      if (url.pathname === "/") {
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        return res.end(renderHome());
      }
      if (url.pathname === "/orders") {
        res.writeHead(200, { "content-type": "application/json" });
        return res.end(JSON.stringify(await ordersWithUsers()));
      }
      if (url.pathname === "/search") {
        const q = url.searchParams.get("q") ?? "";
        res.writeHead(200, { "content-type": "application/json" });
        return res.end(JSON.stringify(await search(q)));
      }
      res.writeHead(404);
      res.end("not found");
    } catch (e) {
      res.writeHead(500);
      res.end("error");
    }
  })
  .listen(3100);
