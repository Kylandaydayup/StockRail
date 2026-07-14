# StockRail UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor StockRail's report and admin UI to follow the local `ui-design-kit` token, form, feedback, empty-state, and status-badge patterns while preserving existing business behavior.

**Architecture:** Keep the no-build native HTML/CSS/JavaScript architecture. Add behavioral coverage with Playwright first, then update HTML semantics, CSS tokens/components, and focused JavaScript helpers for field-level errors and status rendering.

**Tech Stack:** Native HTML, CSS custom properties, browser JavaScript modules, Node test runner, Python unittest, Playwright.

---

## File Map

- `docs/superpowers/specs/2026-07-14-stockrail-ui-redesign-design.md`: approved design scope and acceptance criteria.
- `docs/superpowers/specs/2026-07-14-stockrail-ui-redesign-test-plan.md`: verification strategy.
- `e2e/stockrail-ui-redesign.spec.ts`: create targeted browser tests for login, report submission, validation, admin list/detail/status, and visual viewport checks.
- `index.html`: modify report page structure and add stable field error nodes.
- `admin.html`: modify admin workspace shell, filter toolbar classes, and panel wrappers.
- `login.html`: apply minimal shared class alignment when global controls change.
- `src/styles.css`: replace the old ad hoc theme with design-kit-like tokens and component classes.
- `src/app.js`: update field-level error rendering, item-card markup, loading labels, and success feedback hooks.
- `src/admin.js`: add status badge rendering, empty-state helpers, render error handling, and consistent admin markup.

## Task 1: Add Browser Coverage For Current Critical Flows

**Files:**
- Create: `e2e/stockrail-ui-redesign.spec.ts`
- Modify: none
- Test: `e2e/stockrail-ui-redesign.spec.ts`

- [ ] **Step 1: Write the failing Playwright tests**

Create `e2e/stockrail-ui-redesign.spec.ts` with this content:

```ts
import { expect, test } from '@playwright/test';

const adminUser = process.env.STOCKRAIL_SUPERADMIN_USER || 'root';
const adminPassword = process.env.STOCKRAIL_SUPERADMIN_PASSWORD || 'RootPass123!';

async function login(page, username: string, password: string) {
  await page.goto('/login');
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole('button', { name: '登录' }).click();
}

async function createUser(page, email: string, password: string, role: 'member' | 'admin' | 'superadmin') {
  await page.goto('/admin');
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('select[name="role"]').selectOption(role);
  await page.getByRole('button', { name: '创建用户' }).click();
  await expect(page.locator('#user-list')).toContainText(email);
}

async function fillValidReport(page, suffix = Date.now().toString()) {
  await page.locator('input[name="wechatName"]').fill(`测试用户${suffix}`);
  await page.locator('select[name="deliveryMethod"]').selectOption('快递/物流');
  await page.locator('textarea[name="trackingNumbers"]').fill(`中通${suffix}`);
  await page.locator('input[name="totalBoxes"]').fill('2');
  await page.locator('.item-card').first().locator('input[name="brand"]').fill('皇家');
  await page.locator('.item-card').first().locator('input[name="product"]').fill('皇家A2');
  await page.locator('.item-card').first().locator('input[name="quantity"]').fill('12');
  await page.locator('input[name="totalCans"]').fill('12');
  await page.locator('input[name="phone"]').fill('13800138000');
  await page.locator('textarea[name="remark"]').fill('瘪2个');
}

test.describe('StockRail redesigned flows', () => {
  test('member sees field-level validation and submits a report', async ({ page }) => {
    const memberEmail = `member-${Date.now()}@example.com`;
    const memberPassword = 'MemberPass123!';

    await login(page, adminUser, adminPassword);
    await createUser(page, memberEmail, memberPassword, 'member');
    await page.getByRole('button', { name: '退出' }).click();

    await login(page, memberEmail, memberPassword);
    await expect(page).toHaveURL(/\/$/);

    await page.getByRole('button', { name: '提交报单' }).click();
    await expect(page.locator('#form-error')).toContainText('请填写微信名字');
    await expect(page.locator('input[name="wechatName"]')).toBeFocused();

    await fillValidReport(page);
    await page.getByRole('button', { name: '提交报单' }).click();
    await expect(page.locator('#success-sheet')).toBeVisible();
    await expect(page.locator('#success-sheet')).toContainText('报单已提交');
  });

  test('admin filters, opens detail, and updates order status', async ({ page }) => {
    const memberEmail = `member-${Date.now()}@example.com`;
    const memberPassword = 'MemberPass123!';
    const orderSuffix = Date.now().toString();

    await login(page, adminUser, adminPassword);
    await createUser(page, memberEmail, memberPassword, 'member');
    await page.getByRole('button', { name: '退出' }).click();

    await login(page, memberEmail, memberPassword);
    await fillValidReport(page, orderSuffix);
    await page.getByRole('button', { name: '提交报单' }).click();
    await expect(page.locator('#success-sheet')).toBeVisible();

    await page.goto('/login');
    await login(page, adminUser, adminPassword);
    await page.goto('/admin');
    await page.locator('input[name="keyword"]').fill(`中通${orderSuffix}`);
    await page.getByRole('button', { name: '筛选' }).click();
    await expect(page.locator('#order-list')).toContainText(`测试用户${orderSuffix}`);

    await page.locator('#order-list tr[data-id]').first().click();
    await expect(page.locator('#order-detail')).toContainText(`测试用户${orderSuffix} 的入库报单`);
    await page.getByRole('button', { name: '标记核对中' }).click();
    await expect(page.locator('#order-detail')).toContainText('核对中');
    await page.getByRole('button', { name: '标记已入库' }).click();
    await expect(page.locator('#order-detail')).toContainText('已入库');
  });

  test('key pages render without horizontal overflow at target viewports', async ({ page }) => {
    const viewports = [
      { width: 375, height: 812, path: '/' },
      { width: 390, height: 844, path: '/admin' },
      { width: 1280, height: 800, path: '/login' },
    ];

    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(viewport.path);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(overflow, `${viewport.path} overflows at ${viewport.width}px`).toBe(false);
    }
  });
});
```

- [ ] **Step 2: Run the new test to verify it fails on missing app seed/config or missing UI behavior**

Run:

```bash
STOCKRAIL_SUPERADMIN_USER=root STOCKRAIL_SUPERADMIN_EMAIL=root@example.com STOCKRAIL_SUPERADMIN_PASSWORD='RootPass123!' STOCKRAIL_SESSION_SECRET='test-secret' npm start
```

In a second shell, run:

```bash
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/stockrail-ui-redesign.spec.ts
```

Expected: at least the field-level assertion or overflow assertion fails before the UI redesign, while the server remains reachable.

- [ ] **Step 3: Commit the failing coverage**

```bash
git add e2e/stockrail-ui-redesign.spec.ts
git commit -m "test: add StockRail UI redesign e2e coverage"
```

## Task 2: Introduce Design Tokens And Base Controls

**Files:**
- Modify: `src/styles.css`
- Test: `e2e/stockrail-ui-redesign.spec.ts`

- [ ] **Step 1: Add the design-kit token layer and shared control classes**

Modify the top of `src/styles.css` so it starts with this token layer, keeping later page-specific selectors below it for now:

```css
:root {
  color-scheme: light;
  --radius: 0.625rem;
  --background: #f7f8fa;
  --foreground: #171717;
  --card: #ffffff;
  --card-foreground: #171717;
  --popover: #ffffff;
  --popover-foreground: #171717;
  --primary: #1f2937;
  --primary-foreground: #ffffff;
  --secondary: #f3f4f6;
  --secondary-foreground: #1f2937;
  --muted: #f3f4f6;
  --muted-foreground: #667085;
  --accent: #eef4ff;
  --accent-foreground: #1d4ed8;
  --destructive: #dc2626;
  --destructive-foreground: #ffffff;
  --success: #16a34a;
  --success-foreground: #ffffff;
  --warning: #d97706;
  --warning-foreground: #111827;
  --info: #2563eb;
  --info-foreground: #ffffff;
  --neutral: #6b7280;
  --neutral-foreground: #ffffff;
  --border: #e5e7eb;
  --input: #d1d5db;
  --ring: #94a3b8;
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --shadow-soft: 0 1px 2px rgba(15, 23, 42, 0.06);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--background);
  color: var(--foreground);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
}

button,
input,
textarea,
select {
  font: inherit;
}

button,
a {
  -webkit-tap-highlight-color: transparent;
}

input,
textarea,
select {
  width: 100%;
  border: 1px solid var(--input);
  border-radius: var(--radius-md);
  background: var(--card);
  color: var(--foreground);
  outline: 0;
  transition: border-color 150ms ease, box-shadow 150ms ease, background 150ms ease;
}

input,
select {
  min-height: 40px;
  padding: 0 12px;
}

textarea {
  min-height: 76px;
  padding: 10px 12px;
  resize: vertical;
}

input:focus,
textarea:focus,
select:focus {
  border-color: var(--ring);
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.28);
}

[aria-invalid="true"] {
  border-color: var(--destructive);
}

[aria-invalid="true"]:focus {
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.16);
}

::placeholder {
  color: #9ca3af;
}

.button,
button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: var(--primary-foreground);
  font-weight: 600;
  cursor: pointer;
  transition: border-color 150ms ease, background 150ms ease, color 150ms ease, opacity 150ms ease;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.button-secondary {
  border-color: var(--border);
  background: var(--secondary);
  color: var(--secondary-foreground);
}

.button-outline {
  border-color: var(--border);
  background: var(--card);
  color: var(--foreground);
}

.button-ghost {
  border-color: transparent;
  background: transparent;
  color: var(--foreground);
}

.button-destructive {
  background: var(--destructive);
  color: var(--destructive-foreground);
}

.field-error {
  min-height: 18px;
  margin: 6px 0 0;
  color: var(--destructive);
  font-size: 12px;
  line-height: 1.5;
}

.alert-banner,
.empty-state,
.loading-state {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card);
  color: var(--card-foreground);
}

.status-badge {
  display: inline-flex;
  min-height: 24px;
  align-items: center;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

.status-badge.neutral {
  background: var(--muted);
  color: var(--muted-foreground);
}

.status-badge.warning {
  background: rgba(217, 119, 6, 0.14);
  color: #92400e;
}

.status-badge.info {
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
}

.status-badge.success {
  background: rgba(22, 163, 74, 0.13);
  color: #15803d;
}
```

- [ ] **Step 2: Remove duplicated legacy root and global input rules**

In `src/styles.css`, delete the old `:root`, `*`, `body`, `button,input,textarea,select`, `button,a`, generic `input, textarea, select`, generic `input, select`, `textarea`, `select`, and `::placeholder` blocks that conflict with the new token layer.

- [ ] **Step 3: Run CSS-independent tests**

Run:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 4: Commit token work**

```bash
git add src/styles.css
git commit -m "style: add StockRail design tokens"
```

## Task 3: Refactor Report Page Markup And Field Errors

**Files:**
- Modify: `index.html`
- Modify: `src/app.js`
- Modify: `src/styles.css`
- Test: `e2e/stockrail-ui-redesign.spec.ts`

- [ ] **Step 1: Update report form markup with stable field error nodes**

In `index.html`, replace each report field label with a `.field-row` containing a `.field-control` wrapper and a field error node. The `wechatName` field should look like this pattern:

```html
<label class="field-row" data-field="wechatName">
  <span>微信名字</span>
  <div class="field-control">
    <input name="wechatName" aria-describedby="wechatName-error" placeholder="结账时能快速在微信上找到你" />
    <p id="wechatName-error" class="field-error" data-error-for="wechatName"></p>
  </div>
</label>
```

Apply the same structure to:

- `deliveryMethod`
- `trackingNumbers`
- `totalBoxes`
- `totalCans`
- `phone`
- `remark`

For `deliveryMethod`, keep class `selectable` on the label and place the `select` inside `.field-control`.

- [ ] **Step 2: Replace dynamic item card markup in `src/app.js`**

Replace the `card.innerHTML` template inside `addItem()` with:

```js
card.innerHTML = `
  <div class="item-head">
    <span class="item-index"></span>
    <div>
      <strong>入库明细</strong>
      <p>品牌、奶粉名称和数量均必填</p>
    </div>
    <div class="item-head-actions">
      <button class="button-ghost compact-button" type="button" data-action="more">说明</button>
      <button class="button-outline compact-button" type="button" data-action="delete">删除</button>
      <button class="button-secondary compact-button" type="button" data-action="collapse">收起</button>
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
    <button type="button" class="button-outline add-record" data-action="add">添加记录</button>
  </div>
`;
```

- [ ] **Step 3: Implement field-level error helpers in `src/app.js`**

Replace `showErrors(errors)` and `clearFieldErrors()` with:

```js
function showErrors(errors) {
  clearFieldErrors();
  const first = Object.values(errors)[0];
  errorNode.textContent = first;
  Object.entries(errors).forEach(([fieldName, message]) => {
    const errorTarget = form.querySelector(`[data-error-for="${fieldName}"]`);
    const inputTarget = form.querySelector(`[name="${fieldName}"]`);
    if (errorTarget) {
      errorTarget.textContent = message;
    }
    if (inputTarget) {
      inputTarget.setAttribute("aria-invalid", "true");
    }
  });
  const fieldName = Object.keys(errors)[0];
  const target = form.querySelector(`[name="${fieldName}"]`) ?? itemsNode.querySelector("input");
  target?.focus();
  showToast(first);
}

function clearFieldErrors() {
  errorNode.textContent = "";
  form.querySelectorAll("[data-error-for]").forEach((node) => {
    node.textContent = "";
  });
  form.querySelectorAll("[aria-invalid]").forEach((node) => {
    node.removeAttribute("aria-invalid");
  });
}
```

- [ ] **Step 4: Update collapse button labels**

In `handleItemAction`, replace collapse label assignments with plain labels:

```js
event.target.textContent = card.classList.contains("is-collapsed") ? "展开" : "收起";
```

In `updateCollapseAllButton`, replace the label with:

```js
collapseAllButton.textContent = hasOpenCard ? "全部收起" : "全部展开";
```

- [ ] **Step 5: Add report page CSS**

In `src/styles.css`, update report-specific selectors so the page uses bordered sections, field controls, compact buttons, and stable cards. Ensure these selectors exist:

```css
.phone-shell {
  width: min(100%, 520px);
  min-height: 100vh;
  margin: 0 auto;
  background: var(--card);
}

.profile-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 0 20px 16px;
}

.field-row {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
  align-items: start;
}

.field-control {
  min-width: 0;
}

.compact-button {
  min-height: 32px;
  padding: 0 10px;
  font-size: 13px;
}

.item-card {
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card);
  box-shadow: var(--shadow-soft);
}

@media (max-width: 420px) {
  .field-row {
    grid-template-columns: 1fr;
  }

  .item-head {
    align-items: flex-start;
  }

  .item-head-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
```

- [ ] **Step 6: Run report e2e test**

Run:

```bash
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/stockrail-ui-redesign.spec.ts -g "member sees field-level validation"
```

Expected: PASS.

- [ ] **Step 7: Commit report page work**

```bash
git add index.html src/app.js src/styles.css e2e/stockrail-ui-redesign.spec.ts
git commit -m "feat: redesign StockRail report form"
```

## Task 4: Refactor Admin Workspace Rendering

**Files:**
- Modify: `admin.html`
- Modify: `src/admin.js`
- Modify: `src/styles.css`
- Test: `e2e/stockrail-ui-redesign.spec.ts`

- [ ] **Step 1: Add admin shell classes in `admin.html`**

Keep the same element IDs, but update the shell classes:

```html
<body class="admin-body">
  <main class="admin-layout">
    <header class="admin-header app-header">
      ...
    </header>
    <section class="admin-grid">
      <aside class="order-list-panel panel">
        ...
      </aside>
      <section id="order-detail" class="order-detail panel">
        ...
      </section>
    </section>
    <section id="user-admin" class="user-admin panel" hidden>
      ...
    </section>
    <section id="audit-admin" class="user-admin panel" hidden>
      ...
    </section>
  </main>
</body>
```

- [ ] **Step 2: Add status badge helper in `src/admin.js`**

Add this helper near `roleSelect`:

```js
function statusBadge(status) {
  const variant = {
    "待处理": "warning",
    "核对中": "info",
    "已入库": "success"
  }[status] || "neutral";
  return `<span class="status-badge ${variant}">${escapeHTML(status)}</span>`;
}
```

- [ ] **Step 3: Use status badges in order list and detail**

In `renderList`, replace:

```js
<td>${escapeHTML(order.status)}</td>
```

with:

```js
<td>${statusBadge(order.status)}</td>
```

In `renderDetail`, replace:

```js
<span class="status-badge">${escapeHTML(order.status)}</span>
```

with:

```js
${statusBadge(order.status)}
```

- [ ] **Step 4: Use consistent empty states**

Replace empty list markup in `renderList` with:

```js
listNode.innerHTML = '<div class="empty-state"><strong>暂无订单</strong><p>当前条件下没有报单。</p></div>';
```

Replace empty detail markup in `renderDetail(null)` with:

```js
detailNode.innerHTML = `
  <div class="empty-state">
    <strong>暂无订单</strong>
    <p>提交报单后，管理员可以在这里查看详情。</p>
  </div>
`;
```

Replace empty audit log markup with:

```js
auditListNode.innerHTML = '<div class="empty-state"><strong>暂无审计日志</strong><p>关键操作发生后会显示在这里。</p></div>';
```

- [ ] **Step 5: Add admin CSS**

In `src/styles.css`, ensure admin layout selectors use the design-token system:

```css
.admin-body {
  background: var(--background);
}

.admin-layout {
  width: min(100% - 32px, 1440px);
  margin: 0 auto;
  padding: 24px 0 40px;
}

.panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card);
}

.admin-grid {
  display: grid;
  grid-template-columns: minmax(420px, 0.95fr) minmax(0, 1.3fr);
  gap: 16px;
  align-items: start;
}

.order-filters {
  display: grid;
  grid-template-columns: minmax(180px, 1.5fr) repeat(4, minmax(120px, 1fr));
  gap: 10px;
}

.order-list,
.user-list {
  overflow-x: auto;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.admin-table th,
.admin-table td {
  border-bottom: 1px solid var(--border);
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
}

.active-row {
  background: var(--accent);
}

.empty-state {
  padding: 28px;
  text-align: center;
}

.empty-state strong {
  display: block;
  margin-bottom: 6px;
  font-size: 15px;
}

.empty-state p {
  margin: 0;
  color: var(--muted-foreground);
  font-size: 14px;
}

@media (max-width: 980px) {
  .admin-layout {
    width: min(100% - 24px, 720px);
  }

  .admin-grid,
  .order-filters {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run admin e2e test**

Run:

```bash
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/stockrail-ui-redesign.spec.ts -g "admin filters"
```

Expected: PASS.

- [ ] **Step 7: Commit admin work**

```bash
git add admin.html src/admin.js src/styles.css
git commit -m "feat: redesign StockRail admin workspace"
```

## Task 5: Align Login Page And Verify Viewports

**Files:**
- Modify: `login.html`
- Modify: `src/styles.css`
- Test: `e2e/stockrail-ui-redesign.spec.ts`

- [ ] **Step 1: Align login card with shared panel and control styles**

In `login.html`, add `panel` to the login card:

```html
<section class="login-card panel">
```

- [ ] **Step 2: Update auth tab and code row styles**

In `src/styles.css`, ensure these selectors exist:

```css
.login-shell {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
}

.login-card {
  width: min(100%, 420px);
  padding: 28px;
}

.auth-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  margin: 20px 0;
  border-radius: var(--radius-md);
  background: var(--muted);
  padding: 4px;
}

.auth-tabs button {
  min-height: 36px;
  border-color: transparent;
  background: transparent;
  color: var(--muted-foreground);
}

.auth-tabs button.active {
  background: var(--card);
  color: var(--foreground);
  box-shadow: var(--shadow-soft);
}

.auth-panel {
  display: grid;
  gap: 14px;
}

.auth-panel[hidden] {
  display: none;
}

.code-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

@media (max-width: 420px) {
  .login-card {
    padding: 22px;
  }

  .code-row {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: Run viewport overflow e2e test**

Run:

```bash
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/stockrail-ui-redesign.spec.ts -g "key pages render"
```

Expected: PASS.

- [ ] **Step 4: Commit login alignment**

```bash
git add login.html src/styles.css
git commit -m "style: align StockRail auth page"
```

## Task 6: Full Verification And Completion Audit

**Files:**
- Modify: none unless verification reveals a defect.
- Test: all relevant suites.

- [ ] **Step 1: Run unit and server tests**

Run:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 2: Run full Playwright suite**

Run the server:

```bash
STOCKRAIL_SUPERADMIN_USER=root STOCKRAIL_SUPERADMIN_EMAIL=root@example.com STOCKRAIL_SUPERADMIN_PASSWORD='RootPass123!' STOCKRAIL_SESSION_SECRET='test-secret' npm start
```

In a second shell:

```bash
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright test
```

Expected: PASS.

- [ ] **Step 3: Capture QA screenshots**

Run:

```bash
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright screenshot --viewport-size=375,812 http://127.0.0.1:4173/ /tmp/stockrail-report-mobile.png
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright screenshot --viewport-size=390,844 http://127.0.0.1:4173/admin /tmp/stockrail-admin-mobile.png
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright screenshot --viewport-size=1440,900 http://127.0.0.1:4173/admin /tmp/stockrail-admin-desktop.png
PLAYWRIGHT_TEST_BASE_URL=http://127.0.0.1:4173 npx playwright screenshot --viewport-size=1280,800 http://127.0.0.1:4173/login /tmp/stockrail-login-desktop.png
```

Expected: screenshots are created. Inspect them for overlap, clipping, unreadable text, and one-note color usage.

- [ ] **Step 4: Inspect changed files**

Run:

```bash
git status --short
git diff --stat
git diff --check
```

Expected: only planned UI/test files are changed, and `git diff --check` returns no whitespace errors.

- [ ] **Step 5: Commit final fixes if needed**

If verification required fixes, commit them:

```bash
git add index.html admin.html login.html src/app.js src/admin.js src/styles.css e2e/stockrail-ui-redesign.spec.ts
git commit -m "fix: polish StockRail UI redesign"
```

If no fixes were needed, do not create an empty commit.

## Self-Review

Spec coverage:

- Design-token migration is covered by Task 2.
- User report page structure, field-level errors, item-card behavior, and submission feedback are covered by Task 3.
- Admin master-detail layout, filters, status badges, empty states, superadmin sections, and status updates are covered by Task 4.
- Login/register visual alignment is covered by Task 5.
- Automated, e2e, and visual QA evidence are covered by Tasks 1 and 6.

No placeholders:

- The plan contains concrete files, commands, expected outcomes, and code snippets for the core implementation changes.

Type and selector consistency:

- The plan preserves existing IDs used by JavaScript: `#order-form`, `#items`, `#form-error`, `#success-sheet`, `#order-list`, `#order-detail`, `#order-filters`, `#user-admin`, and `#audit-admin`.
- New reusable selectors are consistent across tasks: `.panel`, `.empty-state`, `.status-badge`, `.field-error`, `.field-control`, `.compact-button`.
