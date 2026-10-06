// Offline browser regression check. Requires Node and Playwright (see web README).
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({channel: process.env.SAGEQL_TEST_BROWSER || 'chrome', headless: true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const html = await fs.readFile(path.join(__dirname, '../examples/web/index.html'), 'utf8');
    let calls = 0, sessions = 0, mode = 'rahtal';
    const report = {title: 'نتیجه آزمایشی', revision: 2, fields: [{id: 'count', label: 'تعداد', type: 'integer'}], rows: [[3]], visualization: {kind: 'table'}, provenance: {}};
    const trace = (id, reply_status, extra = {}) => ({id, saved: true, started_at: '2026-10-06T10:00:00Z', events: [
      {stage: 'request', status: 'started', elapsed_ms: 0},
      {stage: 'interpretation', status: 'started', elapsed_ms: 1},
      {stage: 'interpretation', status: 'complete', elapsed_ms: 3, duration_ms: 2},
      ...(reply_status === 'failed' ? [{stage: 'connection', status: 'started', elapsed_ms: 4}] : []),
      {stage: 'request', status: reply_status === 'failed' ? 'failed' : 'complete', elapsed_ms: 8, duration_ms: 8, reply_status, ...extra},
    ]});
    const replies = [
      {revision: 1, assistant: {text: 'Which year?'}, diagnostics: trace('clarification', 'needs_clarification')},
      {revision: 2, assistant: {text: 'Done'}, report, diagnostics: trace('success', 'report_ready', {row_count: 1})},
      {revision: 2, assistant: {text: 'Connection unavailable'}, error: {code: 'database_unavailable', retryable: true}, diagnostics: trace('failure', 'failed', {error: {code: 'database_unavailable'}, note: '<img src=x onerror=alert(1)>'})},
      {revision: 2, assistant: {text: 'Cached'}, report, diagnostics: {id: 'cached', saved: true, events: [{stage: 'retry', status: 'cached', elapsed_ms: 1}, {stage: 'request', status: 'complete', reply_status: 'report_ready', elapsed_ms: 2}]}},
    ];
    await page.route('http://127.0.0.1:8766/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: html});
      let payload;
      if (url.pathname === '/config') payload = {mode, requires_auth: false};
      else if (url.pathname === '/report-sessions') payload = {session_id: `test-${++sessions}`, revision: 0, assistant: {text: 'Ask a question'}};
      else if (url.pathname.endsWith('/messages')) payload = replies[calls++];
      else throw new Error('Unexpected route ' + url.pathname);
      await route.fulfill({contentType: 'application/json', body: JSON.stringify(payload)});
    });
    await page.goto('http://127.0.0.1:8766/');
    await page.locator('#send').waitFor({state: 'visible'});
    await page.waitForFunction(() => !document.getElementById('send').disabled);
    assert.equal(await page.locator('html').getAttribute('lang'), 'fa');
    assert.equal(await page.locator('html').getAttribute('dir'), 'rtl');
    await page.getByRole('tab', {name: 'مراحل و جزئیات اجرا', exact: true}).click();
    assert.equal(await page.locator('#diagnostics-empty').isVisible(), true);
    assert.equal(await page.locator('#result-view').isVisible(), false);
    await page.getByRole('tab', {name: 'مراحل و جزئیات اجرا', exact: true}).press('Home');
    assert.equal(await page.locator('#result-tab').getAttribute('aria-selected'), 'true');
    async function send(message, expectedAttempts) {
      await page.locator('#message').fill(message);
      await page.locator('#send').click();
      await page.waitForFunction(count => document.getElementById('trace-select').options.length === count && !document.getElementById('send').disabled, expectedAttempts);
    }
    await send('Synthetic question', 1);
    await page.locator('#logs-tab').click();
    assert.equal(await page.locator('#diagnostics-summary').textContent(), 'نیاز به پاسخ تکمیلی');
    assert.equal(await page.locator('.trace-step').count(), 2); // Started/completed events pair.
    await send('2026', 2);
    await page.locator('#result-tab').click();
    assert.equal(await page.locator('#table td').textContent(), '۳');
    await send('Refine', 3);
    assert.equal(await page.locator('#table td').textContent(), '۳'); // Failure keeps successful result.
    await page.locator('#logs-tab').click();
    assert.equal(await page.locator('#diagnostics-summary').textContent(), 'ناموفق');
    assert.equal(await page.getByText('پایان مرحله ثبت نشده است', {exact: false}).count(), 1);
    assert.equal(await page.locator('#diagnostics img').count(), 0); // Trace text is not executable HTML.
    await page.locator('#trace-select').selectOption('0');
    assert.equal(await page.locator('#diagnostics-summary').textContent(), 'نیاز به پاسخ تکمیلی');
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#download-trace').click();
    const download = await downloadPromise;
    assert.equal(download.suggestedFilename(), 'rahtal-trace-clarification.json');
    const downloaded = JSON.parse(await fs.readFile(await download.path(), 'utf8'));
    assert.equal(downloaded.id, 'clarification');
    assert.equal(calls, 3); // Navigation, history and download never submit a report.
    await page.locator('#retry').click();
    await page.waitForFunction(() => document.getElementById('trace-select').options.length === 4);
    assert.equal(await page.getByText('استفاده از پاسخ ذخیره‌شده', {exact: false}).count(), 1);
    const precise = {title: 'گزارش آزمایشی', revision: 3,
      fields: [{id: 'date', label: 'تاریخ', type: 'date'}, {id: 'hours', label: 'ساعات', type: 'decimal'}, {id: 'name', label: 'نام', type: 'text'}],
      rows: [['2026-09-01', '12345678901234567890.123456789', 'علي‌۱۲']], visualization: {kind: 'table'},
      provenance: {period_start: '2026-09-01', period_end_exclusive: '2026-10-01'}};
    await page.evaluate(data => renderReport(data), precise);
    await page.locator('#result-tab').click();
    assert.deepEqual(await page.locator('#table td').allTextContents(), ['۲۰۲۶-۰۹-۰۱', '۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰.۱۲۳۴۵۶۷۸۹', 'علي‌۱۲']);
    assert.equal(precise.rows[0][1], '12345678901234567890.123456789');
    assert.match(await page.locator('#provenance').textContent(), /بازه میلادی/);
    if (process.env.SAGEQL_TEST_SCREENSHOT) await page.screenshot({path: process.env.SAGEQL_TEST_SCREENSHOT, fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('#new-chat').click();
    await page.waitForFunction(() => document.getElementById('trace-select').options.length === 0);
    assert.equal(await page.locator('#result-view').isVisible(), true);
    await page.locator('#logs-tab').click();
    assert.equal(await page.locator('#diagnostics-empty').isVisible(), true);
    for (const nextMode of ['demo', 'sqlserver']) {
      mode = nextMode;
      await page.reload();
      await page.waitForFunction(() => !document.getElementById('send').disabled);
      assert.equal(await page.locator('#workspace-tabs').isVisible(), false);
      assert.equal(await page.locator('#result-view').isVisible(), true);
    }
    assert.deepEqual(errors, []);
    console.log('Passed: tabs, history, failures, cached retries, download, mobile layout and other modes.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
