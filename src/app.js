import { api, requireSession } from "./api.js";
import { readAvatarFile } from "./image-upload.js";
import { validateOrder } from "./storage.js";

const form = document.querySelector("#order-form");
const itemsNode = document.querySelector("#items");
const errorNode = document.querySelector("#form-error");
const successSheet = document.querySelector("#success-sheet");
const newOrderButton = document.querySelector("#new-order");
const collapseAllButton = document.querySelector("#collapse-all");
const quickAddButton = document.querySelector("#quick-add");
const currentUserButton = document.querySelector("#current-user");
const avatarFileInput = document.querySelector("#avatar-file");
const closePageButton = document.querySelector("#close-page");
const invitePanel = document.querySelector("#invite-panel");
const inviteCountNode = document.querySelector("#invite-count");
const inviteLinkTextNode = document.querySelector("#invite-link-text");
const copyInviteButton = document.querySelector("#copy-invite");
const toastNode = document.querySelector("#toast");
const submitButton = form.querySelector('[type="submit"]');
let toastTimer = 0;

const currentUser = await requireSession(["member", "admin", "superadmin"]);
if (currentUser) {
  currentUserButton.innerHTML = userBadge(currentUser);
  addItem();
  loadInvite();
}

closePageButton.addEventListener("click", () => {
  showToast("当前页面可以直接关闭浏览器标签");
});

currentUserButton.addEventListener("click", () => {
  showToast(`${currentUser.nickname || currentUser.username}，当前身份：${roleLabel(currentUser.role)}`);
});

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

quickAddButton.addEventListener("click", () => {
  addItem();
  showToast("已新增 1 条入库明细");
});
copyInviteButton.addEventListener("click", async () => {
  const link = copyInviteButton.dataset.link || "";
  if (!link) {
    showToast("邀请链接还没有加载完成");
    return;
  }
  try {
    await copyText(link);
    copyInviteButton.textContent = "已复制";
    showToast("邀请链接已复制");
    setTimeout(() => {
      copyInviteButton.textContent = "复制邀请链接";
    }, 1800);
  } catch {
    selectInviteLink();
    copyInviteButton.textContent = "已选中";
    showToast("链接已选中，请复制");
    setTimeout(() => {
      copyInviteButton.textContent = "复制邀请链接";
    }, 1800);
  }
});
collapseAllButton.addEventListener("click", () => {
  const cards = [...itemsNode.querySelectorAll(".item-card")];
  const shouldCollapse = cards.some((card) => !card.classList.contains("is-collapsed"));
  cards.forEach((card) => card.classList.toggle("is-collapsed", shouldCollapse));
  collapseAllButton.textContent = shouldCollapse ? "⌄ 全部展开" : "⌃ 全部收起";
  showToast(shouldCollapse ? "已收起全部明细" : "已展开全部明细");
});

newOrderButton.addEventListener("click", () => {
  successSheet.hidden = true;
  form.reset();
  itemsNode.innerHTML = "";
  addItem();
  showToast("可以继续填写新报单");
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
    submitButton.disabled = true;
    submitButton.textContent = "提交中...";
    await api("/api/orders", { method: "POST", body: draft });
    successSheet.hidden = false;
    showToast("报单已提交");
  } catch (error) {
    showErrors(error.fields && Object.keys(error.fields).length ? error.fields : { form: error.message });
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "提交报单";
  }
});

function addItem() {
  const card = document.createElement("article");
  card.className = "item-card";
  card.innerHTML = `
    <div class="item-head">
      <span class="item-index"></span>
      <div class="item-head-actions">
        <button type="button" data-action="more">更多</button>
        <button type="button" data-action="delete">删除</button>
        <button type="button" data-action="collapse">收起 ︿</button>
      </div>
    </div>
    <div class="item-fields">
      <label class="item-field">
        <span><b>*</b>品牌系列</span>
        <input name="brand" placeholder="请输入品牌或系列" />
      </label>
      <label class="item-field">
        <span><b>*</b>奶粉名称</span>
        <input name="product" placeholder="请输入奶粉名称" />
      </label>
      <label class="item-field">
        <span><b>*</b>数量</span>
        <input name="quantity" inputmode="numeric" placeholder="请填写数字" />
      </label>
      <p class="item-helper" hidden>品牌和奶粉名称可以直接输入，不需要从固定选项里找。</p>
      <button type="button" class="add-record" data-action="add">＋ 添加记录</button>
    </div>
  `;
  card.addEventListener("click", handleItemAction);
  itemsNode.append(card);
  renumberItems();
  updateCollapseAllButton();
}

function handleItemAction(event) {
  const action = event.target?.closest("[data-action]")?.dataset?.action;
  if (!action) {
    return;
  }
  const card = event.currentTarget;
  if (action === "add") {
    addItem();
    showToast("已新增 1 条入库明细");
  }
  if (action === "more") {
    const helper = card.querySelector(".item-helper");
    helper.hidden = !helper.hidden;
    event.target.textContent = helper.hidden ? "更多" : "收起说明";
  }
  if (action === "delete") {
    if (itemsNode.children.length === 1) {
      clearItemInputs(card);
      showToast("至少保留 1 条明细，已清空当前内容");
      return;
    }
    card.remove();
    renumberItems();
    updateCollapseAllButton();
    showToast("已删除该条明细");
  }
  if (action === "collapse") {
    card.classList.toggle("is-collapsed");
    event.target.textContent = card.classList.contains("is-collapsed") ? "展开 ﹀" : "收起 ︿";
    updateCollapseAllButton();
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
  const target = form.querySelector(`[name="${fieldName}"]`) ?? itemsNode.querySelector("input");
  target?.focus();
  showToast(first);
}

function clearFieldErrors() {
  errorNode.textContent = "";
}

function clearItemInputs(card) {
  card.querySelectorAll("input").forEach((input) => {
    input.value = "";
  });
}

function renumberItems() {
  [...itemsNode.querySelectorAll(".item-index")].forEach((node, index) => {
    node.textContent = String(index + 1);
  });
}

function updateCollapseAllButton() {
  const cards = [...itemsNode.querySelectorAll(".item-card")];
  const hasOpenCard = cards.some((card) => !card.classList.contains("is-collapsed"));
  collapseAllButton.textContent = hasOpenCard ? "⌃ 全部收起" : "⌄ 全部展开";
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
    inviteLinkTextNode.textContent = invite.inviteLink;
  } catch {
    invitePanel.hidden = true;
  }
}

function escapeAttribute(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}

function showToast(message) {
  clearTimeout(toastTimer);
  toastNode.textContent = message;
  toastNode.hidden = false;
  toastTimer = setTimeout(() => {
    toastNode.hidden = true;
  }, 1800);
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("copy failed");
  }
}

function selectInviteLink() {
  const selection = window.getSelection();
  if (!selection || !inviteLinkTextNode.textContent) {
    return;
  }
  const range = document.createRange();
  range.selectNodeContents(inviteLinkTextNode);
  selection.removeAllRanges();
  selection.addRange(range);
}
