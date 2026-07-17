import { expect, test } from '@playwright/test';

const adminUser = process.env.STOCKRAIL_SUPERADMIN_USER || 'root';
const adminPassword = process.env.STOCKRAIL_SUPERADMIN_PASSWORD || 'RootPass123!';

async function login(page, username: string, password: string) {
  await page.goto('/login');
  const loginForm = page.locator('#login-form');
  await loginForm.locator('input[name="username"]').fill(username);
  await loginForm.locator('input[name="password"]').fill(password);
  await Promise.all([
    page.waitForURL((url) => url.pathname !== '/login'),
    loginForm.getByRole('button', { name: '登录' }).click(),
  ]);
}

async function createUser(page, email: string, password: string, role: 'member' | 'admin' | 'superadmin') {
  await page.goto('/admin');
  const userForm = page.locator('#user-form');
  await userForm.locator('input[name="email"]').fill(email);
  await userForm.locator('input[name="password"]').fill(password);
  await userForm.locator('select[name="role"]').selectOption(role);
  await userForm.getByRole('button', { name: '创建用户' }).click();
  await expect(page.locator('#user-list')).toContainText(email);
}

async function fillValidReport(page, suffix = Date.now().toString()) {
  await page.locator('textarea[name="trackingNumbers"]').fill(`上海市浦东新区示例路 ${suffix} 号`);
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
    await expect(page.locator('#admin-link')).toBeHidden();
    await expect(page.locator('input[name="wechatName"]')).toHaveCount(0);
    await expect(page.locator('select[name="deliveryMethod"]')).toHaveCount(0);
    await expect(page.getByRole('button', { name: '说明' })).toHaveCount(0);
    await expect(page.locator('#invite-panel')).toBeHidden();
    await page.locator('#current-user').click();
    await expect(page.getByRole('button', { name: '邀请码' })).toBeVisible();
    await page.getByRole('button', { name: '邀请码' }).click();
    await expect(page.locator('#invite-panel')).toBeVisible();
    await expect(page.locator('#invite-link-text')).toContainText('/login?invite=');

    await page.getByRole('button', { name: '提交报单' }).click();
    await expect(page.locator('#form-error')).toContainText('请填写快递地址');
    await expect(page.locator('[data-error-for="trackingNumbers"]')).toContainText('请填写快递地址');
    await expect(page.locator('textarea[name="trackingNumbers"]')).toBeFocused();

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
    await page.goto('/');
    await expect(page.locator('#admin-link')).toBeVisible();
    await page.goto('/admin');
    await page.locator('input[name="keyword"]').fill(`示例路 ${orderSuffix}`);
    await page.getByRole('button', { name: '筛选' }).click();
    await expect(page.locator('#order-list')).toContainText(memberEmail);

    await page.locator('#order-list tr[data-id]').first().click();
    await expect(page.locator('#order-detail')).toContainText(`${memberEmail} 的入库报单`);
    await page.getByRole('button', { name: '标记核对中' }).click();
    await expect(page.locator('#order-detail')).toContainText('核对中');
    await page.getByRole('button', { name: '标记已入库' }).click();
    await expect(page.locator('#order-detail')).toContainText('已入库');
  });

  test('key pages render without horizontal overflow at target viewports', async ({ page }) => {
    const memberEmail = `viewport-member-${Date.now()}@example.com`;
    const memberPassword = 'MemberPass123!';

    await page.setViewportSize({ width: 1280, height: 800 });
    await login(page, adminUser, adminPassword);
    await createUser(page, memberEmail, memberPassword, 'member');
    await Promise.all([
      page.waitForURL(/\/login$/),
      page.getByRole('button', { name: '退出' }).click(),
    ]);

    await page.setViewportSize({ width: 375, height: 812 });
    await login(page, memberEmail, memberPassword);
    let overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow, 'report page overflows at 375px').toBe(false);

    await login(page, adminUser, adminPassword);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/admin');
    overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow, 'admin page overflows at 390px').toBe(false);

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/login');
    overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow, 'login page overflows at 1280px').toBe(false);
  });
});
