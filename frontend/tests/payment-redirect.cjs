const assert = require('node:assert/strict');
async function main() {
  const { paymentDestination } = await import('../lib/payment-redirect.ts');
  const origin = 'https://shop.test';
  const authority = 'A' + '1'.repeat(35);
  const valid = `https://payment.zarinpal.com/pg/StartPay/${authority}`;
  assert.equal(paymentDestination('zarinpal', valid, origin), valid);
  assert.equal(paymentDestination('sandbox', '/sandbox-payment/?attempt=12', origin), `${origin}/sandbox-payment/?attempt=12`);
  for (const url of [
    `https://evil.test/pg/StartPay/${authority}`,
    `http://payment.zarinpal.com/pg/StartPay/${authority}`,
    `https://user:secret@payment.zarinpal.com/pg/StartPay/${authority}`,
    `https://payment.zarinpal.com/pg/StartPay/${authority}?next=evil`,
    `https://payment.zarinpal.com/pg/StartPay/${authority}#redirect`,
    `https://payment.zarinpal.com.evil.test/pg/StartPay/${authority}`,
    'javascript:alert(1)',
  ]) assert.equal(paymentDestination('zarinpal', url, origin), null);
  assert.equal(paymentDestination('sandbox', '/sandbox-payment/?attempt=1&redirect=evil', origin), null);
  assert.equal(paymentDestination('sandbox', 'https://evil.test/sandbox-payment/?attempt=1', origin), null);
  assert.equal(paymentDestination('unknown', '/sandbox-payment/?attempt=1', origin), null);
  console.log('Payment redirect boundary checks passed');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
