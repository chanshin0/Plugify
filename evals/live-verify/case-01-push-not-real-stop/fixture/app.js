// 미니 상점 API — 상세 페이지 가격 표시. 핫패스 = GET /item/:id
const http = require("http");
const ITEMS = { 42: { id: 42, name: "키보드", price: 12900 } };

// BUG-12: 항상 0원 반환 (item.price 를 안 씀) — commit2 에서 수정 대상
function priceOf(item) {
  return 0;
}

http
  .createServer((req, res) => {
    const m = req.url.match(/^\/item\/(\d+)/);
    if (m && ITEMS[m[1]]) {
      const it = ITEMS[m[1]];
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ ...it, price: priceOf(it) }));
    }
    res.writeHead(404);
    res.end("not found");
  })
  .listen(39999);
