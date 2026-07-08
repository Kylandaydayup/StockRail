import { api, requireSession } from "./api.js";
import { formatDateTime } from "./storage.js";

const listNode = document.querySelector("#order-list");
const detailNode = document.querySelector("#order-detail");
const refreshButton = document.querySelector("#refresh-orders");
const logoutButton = document.querySelector("#logout");
const adminUserNode = document.querySelector("#admin-user");
const userAdminNode = document.querySelector("#user-admin");
const userForm = document.querySelector("#user-form");
const userListNode = document.querySelector("#user-list");
const userErrorNode = document.querySelector("#user-error");

let selectedID = new URLSearchParams(window.location.search).get("id");
let orders = [];
let currentUser = await requireSession(["admin", "superadmin"]);

if (currentUser) {
  adminUserNode.textContent = `${currentUser.username} · ${currentUser.role}`;
  userAdminNode.hidden = currentUser.role !== "superadmin";
  await render();
}

refreshButton.addEventListener("click", () => render());
logoutButton.addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: {} });
  location.href = "/login.html";
});

userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  userErrorNode.textContent = "";
  const data = new FormData(userForm);
  try {
    await api("/api/users", {
      method: "POST",
      body: {
        username: data.get("username"),
        password: data.get("password"),
        role: data.get("role")
      }
    });
    userForm.reset();
    await renderUsers();
  } catch (error) {
    userErrorNode.textContent = error.message;
  }
});

async function render() {
  const payload = await api("/api/orders");
  orders = payload.orders;
  if (!selectedID && orders[0]) {
    selectedID = orders[0].id;
  }
  renderList(orders);
  if (selectedID) {
    const detail = await api(`/api/orders/${selectedID}`);
    renderDetail(detail.order);
  } else {
    renderDetail(null);
  }
  if (currentUser.role === "superadmin") {
    await renderUsers();
  }
}

function renderList(orders) {
  if (orders.length === 0) {
    listNode.innerHTML = '<div class="empty-detail"><strong>暂无订单</strong><p>先在报单页提交一条记录。</p></div>';
    return;
  }
  listNode.innerHTML = `
    <table class="admin-table order-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>微信名字</th>
          <th>单号</th>
          <th>件数</th>
          <th>罐数</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>
        ${orders.map((order) => `
          <tr class="${order.id === selectedID ? "active-row" : ""}" data-id="${order.id}">
            <td>${formatDateTime(order.createdAt)}</td>
            <td>${escapeHTML(order.wechatName)}</td>
            <td>${escapeHTML(order.trackingNumbers)}</td>
            <td>${order.totalBoxes}</td>
            <td>${order.totalCans}</td>
            <td>${escapeHTML(order.status)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  listNode.querySelectorAll("tr[data-id]").forEach((row) => {
    row.addEventListener("click", async () => {
      selectedID = row.dataset.id;
      await render();
    });
  });
}

function renderDetail(order) {
  if (!order) {
    detailNode.innerHTML = `
      <div class="empty-detail">
        <strong>暂无订单</strong>
        <p>提交报单后，管理员可以在这里查看详情。</p>
      </div>
    `;
    return;
  }

  detailNode.innerHTML = `
    <div class="detail-header">
      <div>
        <h2>${escapeHTML(order.wechatName)} 的入库报单</h2>
        <span class="status-badge">${escapeHTML(order.status)}</span>
      </div>
      <div>${formatDateTime(order.createdAt)}</div>
    </div>

    <div class="detail-grid">
      ${cell("交货方式", order.deliveryMethod)}
      ${cell("快递单号", order.trackingNumbers)}
      ${cell("总件数", `${order.totalBoxes} 箱`)}
      ${cell("总罐数", order.totalCans ? `${order.totalCans} 罐` : "未填写")}
      ${cell("联系方式", order.phone)}
      ${cell("备注", order.remark || "无")}
    </div>

    <h3>入库明细</h3>
    <table class="admin-table">
      <thead>
        <tr>
          <th>#</th>
          <th>品牌系列</th>
          <th>奶粉名称</th>
          <th>数量</th>
        </tr>
      </thead>
      <tbody>
        ${order.items.map((item, index) => `
          <tr>
            <td>${index + 1}</td>
            <td>${escapeHTML(item.brand)}</td>
            <td>${escapeHTML(item.product)}</td>
            <td>${item.quantity}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>

    <div class="status-actions">
      <button type="button" data-status="待处理">标记待处理</button>
      <button type="button" data-status="核对中">标记核对中</button>
      <button type="button" data-status="已入库">标记已入库</button>
    </div>
  `;

  detailNode.querySelectorAll("[data-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/orders/${order.id}/status`, {
        method: "PATCH",
        body: { status: button.dataset.status }
      });
      await render();
    });
  });
}

async function renderUsers() {
  const payload = await api("/api/users");
  userListNode.innerHTML = `
    <table class="admin-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>角色</th>
          <th>创建时间</th>
        </tr>
      </thead>
      <tbody>
        ${payload.users.map((user) => `
          <tr>
            <td>${user.id}</td>
            <td>${escapeHTML(user.username)}</td>
            <td>${escapeHTML(user.role)}</td>
            <td>${formatDateTime(user.createdAt)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function cell(label, value) {
  return `
    <div class="detail-cell">
      <span>${label}</span>
      <strong>${escapeHTML(String(value))}</strong>
    </div>
  `;
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
