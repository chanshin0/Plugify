const { test } = require("node:test");
const assert = require("node:assert");
const { discountRate } = require("./discount");

test("100 미만은 할인 없음", () => assert.equal(discountRate(99), 0));
test("경계 100 은 10% (경계 포함)", () => assert.equal(discountRate(100), 0.1));
test("구간 내(300) 10%", () => assert.equal(discountRate(300), 0.1));
test("경계 500 은 20% (경계 포함)", () => assert.equal(discountRate(500), 0.2));
test("500 초과 20%", () => assert.equal(discountRate(501), 0.2));
