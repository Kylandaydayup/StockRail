import { api, requireSession } from "./api.js";
import { readAvatarFile } from "./image-upload.js";
import { validateOrder } from "./storage.js";

const brands = ["皇家", "爱他美", "美素佳儿", "飞鹤", "君乐宝", "其他"];
const products = ["皇家A2", "卓萃", "佳贝艾特", "星飞帆", "至臻", "其他"];
const form = document.querySelector("#order-form");
const itemsNode = document.querySelector("#items");
const errorNode = document.querySelector("#form-error");
const successSheet = document.querySelector("#success-sheet");
const newOrderButton = document.querySelector("#new-order");
const collapseAllButton = document.querySelector("#collapse-all");
const quickAddButton = document.querySelector("#quick-add");
const currentUserButton = document.querySelector("#current-user");
const avatarFileInput = document.querySelector("#avatar-file");
const invitePanel = document.querySelector("#invite-panel");
const inviteCountNode = document.querySelector("#invite-count");
const copyInviteButton = document.querySelector("#copy-invite");

let itemCounter = 0;

const currentUser = await requireSession(["member", "admin", "superadmin"]);
if (currentUser) {
  currentUserButton.innerHTML = userBadge(currentUser);
  addItem();
  loadInvite();
}

avatarFileInput.addEventListener("change", async () => {
  const file = avatarFileInput.files?.[0];
  if (!file) {
    return;
  }
  clearFieldErrors();
  try {
    const payload = await api("/api/me/profile", {
      method: "PATCH",
      body: {
        nickname: currentUser.nickname || currentUser.username,
        avatarImage: await readAvatarFile(file)
      }
    });
    currentUser.avatarUrl = payload.user.avatarUrl;
    currentUser.nickname = payload.user.nickname;
    currentUserButton.innerHTML = userBadge(currentUser);
    avatarFileInput.value = "";
  } catch (error) {
    showErrors({ form: error.message });
  }
});

quickAddButton.addEventListener("click", () => addItem());
copyInviteButton.addEventListener("click", async () => {
  const link = copyInviteButton.dataset.link || "";
  if (!link) {
    return;
  }
  await navigator.clipboard.writeText(link);
  copyInviteButton.textContent = "已复制";
  setTimeout(() => {
    copyInviteButton.textContent = "复制邀请链接";
  }, 1800);
});
collapseAllButton.addEventListener("click", () => {
  const cards = [...itemsNode.querySelectorAll(".item-card")];
  const shouldCollapse = cards.some((card) => !card.classList.contains("is-collapsed"));
  cards.forEach((card) => card.classList.toggle("is-collapsed", shouldCollapse));
  collapseAllButton.textContent = shouldCollapse ? "⌄ 全部展开" : "⌃ 全部收起";
});

newOrderButton.addEventListener("click", () => {
  successSheet.hidden = true;
  form.reset();
  itemsNode.innerHTML = "";
  itemCounter = 0;
  addItem();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFieldErrors();
  const draft = collectDraft();
  const errors = validateOrder(draft);
  if (Object.keys(errors).length > 0) {
    showErrors(errors);
    return;
  }
  try {
    await api("/api/orders", { method: "POST", body: draft });
    successSheet.hidden = false;
  } catch (error) {
    showErrors(error.fields && Object.keys(error.fields).length ? error.fields : { form: error.message });
  }
});

function addItem() {
  itemCounter += 1;
  const card = document.createElement("article");
  card.className = "item-card";
  card.dataset.item = String(itemCounter);
  card.innerHTML = `
    <div class="item-head">
      <span class="item-index">${itemCounter}</span>
      <div class="item-head-actions">
        <button type="button" data-action="more">更多</button>
        <button type="button" data-action="delete">删除</button>
        <button type="button" data-action="collapse">收起 ︿</button>
      </div>
    </div>
    <div class="item-fields">
      <label class="item-field item-select">
        <span><b>*</b>品牌系列</span>
        <select name="brand">${options(brands, "请选择")}</select>
      </label>
      <label class="item-field item-select">
        <span><b>*</b>奶粉名称</span>
        <select name="product">${options(products, "请选择")}</select>
      </label>
      <label class="item-field">
        <span><b>*</b>数量</span>
        <input name="quantity" inputmode="numeric" placeholder="请填写数字" />
      </label>
      <button type="button" class="add-record" data-action="add">＋ 添加记录</button>
    </div>
  `;
  card.addEventListener("click", handleItemAction);
  itemsNode.append(card);
}

function handleItemAction(event) {
  const action = event.target?.dataset?.action;
  if (!action) {
    return;
  }
  const card = event.currentTarget;
  if (action === "add") {
    addItem();
  }
  if (action === "delete") {
    if (itemsNode.children.length === 1) {
      clearItemInputs(card);
      return;
    }
    card.remove();
    renumberItems();
  }
  if (action === "collapse") {
    card.classList.toggle("is-collapsed");
    event.target.textContent = card.classList.contains("is-collapsed") ? "展开 ﹀" : "收起 ︿";
  }
}

function collectDraft() {
  const data = new FormData(form);
  return {
    wechatName: data.get("wechatName"),
    deliveryMethod: data.get("deliveryMethod"),
    trackingNumbers: data.get("trackingNumbers"),
    totalBoxes: data.get("totalBoxes"),
    totalCans: data.get("totalCans"),
    phone: data.get("phone"),
    remark: data.get("remark"),
    items: [...itemsNode.querySelectorAll(".item-card")].map((card) => ({
      brand: card.querySelector('[name="brand"]').value,
      product: card.querySelector('[name="product"]').value,
      quantity: card.querySelector('[name="quantity"]').value
    }))
  };
}

function showErrors(errors) {
  const first = Object.values(errors)[0];
  errorNode.textContent = first;
  const fieldName = Object.keys(errors)[0];
  const target = form.querySelector(`[name="${fieldName}"]`) ?? itemsNode.querySelector("select, input");
  target?.focus();
}

function clearFieldErrors() {
  errorNode.textContent = "";
}

function options(values, placeholder) {
  const choices = [`<option value="">${placeholder}</option>`];
  choices.push(...values.map((value) => `<option value="${value}">${value}</option>`));
  return choices.join("");
}

function clearItemInputs(card) {
  card.querySelectorAll("input, select").forEach((input) => {
    input.value = "";
  });
}

function renumberItems() {
  [...itemsNode.querySelectorAll(".item-index")].forEach((node, index) => {
    node.textContent = String(index + 1);
  });
}

function roleLabel(role) {
  return {
    member: "会员",
    admin: "管理员",
    superadmin: "超级管理员"
  }[role] || role;
}

function userBadge(user) {
  if (user.avatarUrl) {
    return `<img class="user-avatar" src="${escapeAttribute(user.avatarUrl)}" alt="" />${user.nickname} · ${roleLabel(user.role)}`;
  }
  return `<span>♙</span>${user.nickname || user.username} · ${roleLabel(user.role)}`;
}

async function loadInvite() {
  try {
    const invite = await api("/api/invite");
    invitePanel.hidden = false;
    inviteCountNode.textContent = `已邀请 ${invite.inviteCount || 0} 人`;
    copyInviteButton.dataset.link = invite.inviteLink;
  } catch {
    invitePanel.hidden = true;
  }
}

function escapeAttribute(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}
