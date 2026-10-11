const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:3000';
  const url = new URL(base);
  if (!['127.0.0.1', 'localhost'].includes(url.hostname)) throw new Error('Use a disposable local test server');
  const fixture = JSON.parse(fs.readFileSync(process.env.E2E_SESSION_FILE, 'utf8'));
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await context.addCookies([{name: 'sessionid', value: fixture.buyer, url: base}]);
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    await page.goto(`${base}/products/demo-phone/`);
    await page.getByRole('heading', {name: 'گوشی نمایشی', exact: true}).waitFor();
    const offers = page.getByRole('button', {name: 'افزودن به سبد', exact: true});
    assert.equal(await offers.count(), 2);
    for (let index = 0; index < 2; index++) {
      const response = page.waitForResponse(r => r.url().includes('/commerce/cart/') && r.request().method() === 'POST');
      await offers.nth(index).click();
      assert.equal((await response).status(), 200);
    }
    await page.goto(`${base}/cart/`);
    const checkout = page.getByRole('button', {name: 'تأیید مبلغ و ادامهٔ پرداخت آزمایشی', exact: true});
    await checkout.waitFor();
    await checkout.click();
    await page.waitForURL('**/sandbox-payment/**');
    await page.getByRole('button', {name: 'شبیه‌سازی موفقیت', exact: true}).click();
    await page.getByText('نتیجه: captured', {exact: true}).waitFor();
    const list = await context.request.get(`${base}/api/v1/commerce/orders/`);
    assert.equal(list.status(), 200);
    const orderId = (await list.json()).orders[0].id;
    const detail = await context.request.get(`${base}/api/v1/commerce/orders/${orderId}/`);
    const order = (await detail.json()).order;
    assert.equal(order.status, 'paid');
    assert.equal(order.deliveries.length, 2);

    const staff = await browser.newContext();
    await staff.addCookies([{name: 'sessionid', value: fixture.admin, url: base}]);
    async function command(path, data) {
      assert.equal((await staff.request.get(`${base}/api/v1/auth/csrf/`)).status(), 200);
      const token = (await staff.cookies()).find(cookie => cookie.name === 'csrftoken').value;
      const response = await staff.request.post(base + path, {data, headers: {'X-CSRFToken': token}});
      assert.equal(response.status(), 200, `Command failed: ${path}`);
      return response.json();
    }
    for (const delivery of order.deliveries) {
      for (const status of ['packing', 'shipped', 'delivered']) {
        await command(`/api/v1/operations/deliveries/${delivery.id}/transition/`, {status, reason: 'Browser test fulfillment', tracking_code: `TEST-${delivery.id}`});
      }
    }
    await page.goto(`${base}/orders/`);
    await page.getByRole('button', {name: 'جزئیات', exact: true}).first().click();
    await page.getByText('درخواست مرجوعی', {exact: true}).first().click();
    const form = page.locator('details').first().locator('form');
    await form.locator('textarea[name="reason"]').fill('Damaged test item');
    const createdReturn = page.waitForResponse(r => r.url().includes('/returns/') && r.request().method() === 'POST');
    await form.getByRole('button').click();
    const result = await createdReturn;
    assert.equal(result.status(), 201);
    const returnId = (await result.json()).return.id;
    await command(`/api/v1/operations/returns/${returnId}/decision/`, {status: 'approved', reason: 'Browser test review'});
    await command(`/api/v1/operations/returns/${returnId}/decision/`, {status: 'received', restock: true, reason: 'Browser test inspection'});
    const refunded = await command(`/api/v1/operations/returns/${returnId}/sandbox-refund/`, {reason: 'Browser test simulation'});
    assert.equal(refunded.return.status, 'refunded');
    await page.goto(`${base}/returns/`);
    await page.getByText(/refunded/).waitFor();
    const anonymous = await browser.newContext();
    assert.equal((await anonymous.request.get(`${base}/api/v1/commerce/orders/`)).status(), 401);
    console.log('PASS: mobile two-seller purchase, sandbox capture, fulfillment, return/refund and anonymous isolation');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
