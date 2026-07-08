import test from "node:test";
import assert from "node:assert/strict";

import {
  createOrderStore,
  formatDateTime,
  validateOrder
} from "../src/storage.js";

function memoryStorage() {
  const data = new Map();
  return {
    getItem(key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      data.set(key, String(value));
    },
    removeItem(key) {
      data.delete(key);
    }
  };
}

const validDraft = {
  wechatName: "小王",
  deliveryMethod: "快递/物流",
  trackingNumbers: "中通1234/韵达5678",
  totalBoxes: "3",
  phone: "13800138000",
  totalCans: "18",
  remark: "皇家3-2月/瘪2个",
  items: [
    {
      brand: "皇家",
      product: "皇家A2",
      quantity: "12"
    },
    {
      brand: "爱他美",
      product: "卓萃",
      quantity: "6"
    }
  ]
};

test("validateOrder returns field errors for missing required data", () => {
  const errors = validateOrder({
    wechatName: "",
    trackingNumbers: "",
    totalBoxes: "",
    phone: "",
    items: [{ brand: "", product: "", quantity: "" }]
  });

  assert.equal(errors.wechatName, "请填写微信名字");
  assert.equal(errors.trackingNumbers, "请填写快递单号");
  assert.equal(errors.totalBoxes, "请填写总件数");
  assert.equal(errors.phone, "请填写联系方式");
  assert.equal(errors.items, "请完善第 1 条入库明细");
});

test("createOrder persists normalized orders newest first", () => {
  const store = createOrderStore({
    storage: memoryStorage(),
    now: () => new Date("2026-07-08T01:20:00+08:00"),
    id: () => "order-1"
  });

  const order = store.create(validDraft);

  assert.equal(order.id, "order-1");
  assert.equal(order.status, "待处理");
  assert.equal(order.totalBoxes, 3);
  assert.equal(order.totalCans, 18);
  assert.equal(order.items[0].quantity, 12);
  assert.equal(store.list()[0].id, "order-1");
  assert.deepEqual(store.get("order-1"), order);
});

test("updateStatus changes an existing order status", () => {
  const store = createOrderStore({
    storage: memoryStorage(),
    now: () => new Date("2026-07-08T01:20:00+08:00"),
    id: () => "order-1"
  });

  store.create(validDraft);
  const updated = store.updateStatus("order-1", "已入库");

  assert.equal(updated.status, "已入库");
  assert.equal(store.get("order-1").status, "已入库");
});

test("formatDateTime renders a compact Chinese date time", () => {
  assert.equal(formatDateTime("2026-07-08T01:20:00+08:00"), "2026/07/08 01:20");
});
