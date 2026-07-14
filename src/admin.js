import { api, requireSession } from "./api.js";
import { formatDateTime } from "./storage.js";

const listNode = document.querySelector("#order-list");
const detailNode = document.querySelector("#order-detail");
const refreshButton = document.querySelector("#refresh-orders");
const filterForm = document.querySelector("#order-filters");
const resetFiltersButton = document.querySelector("#reset-filters");
const logoutButton = document.querySelector("#logout");
const adminUserNode = document.querySelector("#admin-user");
const userAdminNode = document.querySelector("#user-admin");
const auditAdminNode = document.querySelector("#audit-admin");
const userForm = document.querySelector("#user-form");
const userListNode = document.querySelector("#user-list");
const userErrorNode = document.querySelector("#user-error");
const auditListNode = document.querySelector("#audit-list");
const refreshAuditButton = document.querySelector("#refresh-audit");

let selectedID = new URLSearchParams(window.location.search).get("id");
let orders = [];
let currentUser = await requireSession(["admin", "superadmin"]);

if (currentUser) {
  adminUserNode.textContent = `${currentUser.nickname || currentUser.username} · ${currentUser.role}`;
  userAdminNode.hidden = currentUser.role !== "superadmin";
  auditAdminNode.hidden = currentUser.role !== "superadmin";
  await render();
}

refreshButton.addEventListener("click", () => render());
filterForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  selectedID = "";
  await render();
});
resetFiltersButton.addEventListener("click", async () => {
  filterForm.reset();
  selectedID = "";
  await render();
});
refreshAuditButton.addEventListener("click", () => renderAuditLogs());
logoutButton.addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: {} });
  location.href = "/login";
});

userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  userErrorNode.textContent = "";
  const data = new FormData(userForm);
  try {
    await api("/api/users", {
      method: "POST",
      body: {
        email: data.get("email"),
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
  const payload = await api(`/api/orders${filterQuery()}`);
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
    await renderAuditLogs();
  }
}

function renderList(orders) {
  if (orders.length === 0) {
    listNode.innerHTML = '<div class="empty-state"><strong>暂无订单</strong><p>当前条件下没有报单。</p></div>';
    return;
  }
  listNode.innerHTML = `
    <table class="admin-table order-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>微信名字</th>
          <th>方式</th>
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
            <td>${escapeHTML(order.deliveryMethod)}</td>
            <td>${escapeHTML(order.trackingNumbers)}</td>
            <td>${order.totalBoxes}</td>
            <td>${order.totalCans}</td>
            <td>${statusBadge(order.status)}</td>
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

function filterQuery() {
  const data = new FormData(filterForm);
  const params = new URLSearchParams();
  ["keyword", "status", "deliveryMethod", "dateFrom", "dateTo"].forEach((name) => {
    const value = String(data.get(name) || "").trim();
    if (value) {
      params.set(name, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

function renderDetail(order) {
  if (!order) {
    detailNode.innerHTML = `
      <div class="empty-state">
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
        ${statusBadge(order.status)}
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
  if (payload.users.length === 0) {
    userListNode.innerHTML = '<div class="empty-state"><strong>暂无用户</strong><p>创建用户后会显示在这里。</p></div>';
    return;
  }
  userListNode.innerHTML = `
    <table class="admin-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>邮箱</th>
          <th>昵称</th>
          <th>角色</th>
          <th>创建时间</th>
        </tr>
      </thead>
      <tbody>
        ${payload.users.map((user) => `
          <tr>
            <td>${user.id}</td>
            <td>${escapeHTML(user.email || user.username)}</td>
            <td>${escapeHTML(user.nickname || "")}</td>
            <td>${roleSelect(user)}</td>
            <td>${formatDateTime(user.createdAt)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  userListNode.querySelectorAll("[data-role-user]").forEach((select) => {
    select.addEventListener("change", async () => {
      await api(`/api/users/${select.dataset.roleUser}/role`, {
        method: "PATCH",
        body: { role: select.value }
      });
      await renderUsers();
    });
  });
}

function roleSelect(user) {
  return `
    <select class="role-select" data-role-user="${user.id}">
      ${["member", "admin", "superadmin"].map((role) => `
        <option value="${role}" ${user.role === role ? "selected" : ""}>${role}</option>
      `).join("")}
    </select>
  `;
}

function statusBadge(status) {
  const variant = {
    "待处理": "warning",
    "核对中": "info",
    "已入库": "success"
  }[status] || "neutral";
  return `<span class="status-badge ${variant}">${escapeHTML(status)}</span>`;
}

async function renderAuditLogs() {
  const payload = await api("/api/audit-logs?limit=100");
  if (payload.logs.length === 0) {
    auditListNode.innerHTML = '<div class="empty-state"><strong>暂无审计日志</strong><p>关键操作发生后会显示在这里。</p></div>';
    return;
  }
  auditListNode.innerHTML = `
    <table class="admin-table audit-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>操作者</th>
          <th>操作</th>
          <th>对象</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody>
        ${payload.logs.map((log) => `
          <tr>
            <td>${formatDateTime(log.createdAt)}</td>
            <td>${escapeHTML(log.actorEmail || "系统")}</td>
            <td>${escapeHTML(actionLabel(log.action))}</td>
            <td>${escapeHTML([log.targetType, log.targetId].filter(Boolean).join(" #"))}</td>
            <td>${escapeHTML(JSON.stringify(log.details || {}))}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function actionLabel(action) {
  return {
    "user.register": "用户注册",
    "user.password.reset": "重置密码",
    "user.profile.update": "修改资料",
    "user.create": "创建用户",
    "user.role.update": "修改角色",
    "order.create": "提交报单",
    "order.status.update": "修改订单状态"
  }[action] || action;
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
