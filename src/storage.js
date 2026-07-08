const STORAGE_KEY = "stockrail.orders.v1";

export function validateOrder(draft) {
  const errors = {};
  if (!text(draft.wechatName)) {
    errors.wechatName = "请填写微信名字";
  }
  if (!text(draft.trackingNumbers)) {
    errors.trackingNumbers = "请填写快递单号";
  }
  if (!positiveNumber(draft.totalBoxes)) {
    errors.totalBoxes = "请填写总件数";
  }
  if (!text(draft.phone)) {
    errors.phone = "请填写联系方式";
  }

  const items = Array.isArray(draft.items) ? draft.items : [];
  if (items.length === 0) {
    errors.items = "请至少添加 1 条入库明细";
    return errors;
  }
  const badIndex = items.findIndex((item) => !text(item.brand) || !text(item.product) || !positiveNumber(item.quantity));
  if (badIndex >= 0) {
    errors.items = `请完善第 ${badIndex + 1} 条入库明细`;
  }
  return errors;
}

export function createOrderStore(options = {}) {
  const storage = options.storage ?? window.localStorage;
  const now = options.now ?? (() => new Date());
  const id = options.id ?? (() => `order-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`);

  function list() {
    return read(storage).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  function save(orders) {
    storage.setItem(STORAGE_KEY, JSON.stringify(orders));
  }

  return {
    list,
    get(orderID) {
      return list().find((order) => order.id === orderID) ?? null;
    },
    create(draft) {
      const errors = validateOrder(draft);
      if (Object.keys(errors).length > 0) {
        const error = new Error("订单信息不完整");
        error.fields = errors;
        throw error;
      }
      const order = normalizeOrder(draft, id(), now());
      save([order, ...read(storage)]);
      return order;
    },
    updateStatus(orderID, status) {
      const orders = read(storage);
      const index = orders.findIndex((order) => order.id === orderID);
      if (index < 0) {
        return null;
      }
      orders[index] = { ...orders[index], status };
      save(orders);
      return orders[index];
    },
    clear() {
      storage.removeItem(STORAGE_KEY);
    }
  };
}

export function formatDateTime(value) {
  const date = new Date(value);
  const parts = [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate())
  ];
  return `${parts.join("/")} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function normalizeOrder(draft, id, createdAt) {
  return {
    id,
    status: "待处理",
    createdAt: createdAt.toISOString(),
    wechatName: text(draft.wechatName),
    deliveryMethod: text(draft.deliveryMethod) || "快递/物流",
    trackingNumbers: text(draft.trackingNumbers),
    totalBoxes: Number(draft.totalBoxes),
    totalCans: numberOrZero(draft.totalCans),
    phone: text(draft.phone),
    remark: text(draft.remark),
    items: draft.items.map((item) => ({
      brand: text(item.brand),
      product: text(item.product),
      quantity: Number(item.quantity)
    }))
  };
}

function read(storage) {
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function text(value) {
  return String(value ?? "").trim();
}

function positiveNumber(value) {
  return Number(value) > 0;
}

function numberOrZero(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function pad(value) {
  return String(value).padStart(2, "0");
}
