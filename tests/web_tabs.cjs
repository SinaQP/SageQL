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
    await page.locator('#topic-example').click();
    assert.match(await page.locator('#message').inputValue(), /هر کارمند روی هر موضوع/);
    await page.locator('#trend-example').click();
    assert.match(await page.locator('#message').inputValue(), /ماه به ماه شمسی/);
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
    const persian = {...precise,
      fields: [{id: 'time_bucket', label: 'ماه', type: 'date'}, {id: 'hours', label: 'ساعات', type: 'number'}],
      rows: [['2026-08-23', 14.583333333333334]],
      provenance: {display_calendar: 'jalali', period_caption: 'شهریور 1405', period_start: '2026-08-23', period_end_exclusive: '2026-09-23'}};
    await page.evaluate(data => renderReport(data), persian);
    assert.deepEqual(await page.locator('#table td').allTextContents(), ['۱۴۰۵/۰۶/۰۱', '۱۴٫۵۸']);
    assert.match(await page.locator('#provenance').textContent(), /شهریور ۱۴۰۵/);
    assert.match(await page.locator('#provenance').textContent(), /۲۰۲۶-۰۸-۲۳/);
    const organization = {...persian, title: 'گزارش کلی سازمان آزمایشی',
      fields: [{id: 'activity_hours', label: 'مجموع ساعات فعالیت', type: 'number', unit: 'ساعت'},
        {id: 'activity_count', label: 'تعداد فعالیت‌های ثبت‌شده', type: 'integer'},
        {id: 'participant_count', label: 'تعداد کارکنان مشارکت‌کننده', type: 'integer'}],
      rows: [[6.136666666666667, 5, 3]], truncated: false};
    await page.evaluate(data => renderReport(data), organization);
    assert.deepEqual(await page.locator('#table td').allTextContents(), ['۶٫۱۴', '۵', '۳']);
    assert.deepEqual(await page.locator('#table th').allTextContents(),
      ['مجموع ساعات فعالیت (ساعت)', 'تعداد فعالیت‌های ثبت‌شده', 'تعداد کارکنان مشارکت‌کننده']);
    assert.equal(await page.locator('#warning').isVisible(), false);
    assert.equal(await page.locator('#chart').isVisible(), false);
    assert.equal(organization.rows[0][0], 6.136666666666667);
    const dailyMatches = {...persian, title: 'روزهای مطابق شرایط آزمایشی',
      fields: [{id: 'time_bucket', label: 'تاریخ', type: 'date'},
        {id: 'employee_name', label: 'نام کامل کارمند', type: 'text'},
        {id: 'activity_hours', label: 'مجموع ساعات فعالیت', type: 'number', unit: 'ساعت'},
        {id: 'matching_day_count', label: 'تعداد روزهای مطابق شرایط', type: 'integer', unit: 'روز'}],
      rows: [['2026-09-21', 'نام آزمایشی', 12.3456789, 3], ['2026-09-22', 'نام آزمایشی', 11.25, 3]],
      truncated: true, provenance: {...persian.provenance, matching_day_count: {
        scope: 'per_entity_per_period', after_aggregate_filters: true, before_output_limit: true}}};
    await page.evaluate(data => renderReport(data), dailyMatches);
    assert.deepEqual(await page.locator('#table td').allTextContents(),
      ['۱۴۰۵/۰۶/۳۰', 'نام آزمایشی', '۱۲٫۳۵', '۳', '۱۴۰۵/۰۶/۳۱', 'نام آزمایشی', '۱۱٫۲۵', '۳']);
    assert.deepEqual(await page.locator('#table th').allTextContents(),
      ['تاریخ', 'نام کامل کارمند', 'مجموع ساعات فعالیت (ساعت)', 'تعداد روزهای مطابق شرایط (روز)']);
    assert.equal(dailyMatches.rows[0][2], 12.3456789);
    assert.equal(await page.locator('#warning').isVisible(), true);
    const dailyBounds = await page.locator('#table th').evaluateAll(headers => headers.map(header => {
      const box = header.getBoundingClientRect(), wrap = header.closest('.table-wrap').getBoundingClientRect();
      return box.left >= wrap.left && box.right <= wrap.right;
    }));
    assert.ok(dailyBounds.every(Boolean), 'All daily matching fields must remain visible.');
    dailyMatches.truncated = false;
    dailyMatches.rows = [['2026-09-22', 'نام آزمایشی', 11.25, 1]];
    await page.evaluate(data => renderReport(data), dailyMatches);
    assert.equal(await page.locator('#warning').isVisible(), false);
    assert.equal(await page.locator('#table tbody tr').count(), 1);
    const positions = {...persian, title: 'توزیع حجم کار سمت‌های آزمایشی',
      fields: [{id: 'job_position', label: 'سمت شغلی فعلی', type: 'text'},
        {id: 'activity_hours', label: 'مجموع ساعات فعالیت', type: 'number', unit: 'ساعت'},
        {id: 'participant_count', label: 'تعداد کارکنان مشارکت‌کننده', type: 'integer'},
        {id: 'average_participant_hours', label: 'میانگین ساعات به‌ازای کارمند مشارکت‌کننده', type: 'number', unit: 'ساعت'}],
      rows: [['سمت آزمایشی', 14.583333333333334, 2, 7.291666666666667], [null, 5, 1, null]], truncated: false};
    await page.evaluate(data => renderReport(data), positions);
    assert.deepEqual(await page.locator('#table td').allTextContents(),
      ['سمت آزمایشی', '۱۴٫۵۸', '۲', '۷٫۲۹', '—', '۵', '۱', '—']);
    assert.deepEqual(await page.locator('#table th').allTextContents(),
      ['سمت شغلی فعلی', 'مجموع ساعات فعالیت (ساعت)', 'تعداد کارکنان مشارکت‌کننده',
        'میانگین ساعات به‌ازای کارمند مشارکت‌کننده (ساعت)']);
    assert.equal(positions.rows[0][3], 7.291666666666667);
    assert.equal(await page.locator('#warning').isVisible(), false);
    const positionBounds = await page.locator('#table th').evaluateAll(headers => headers.map(header => {
      const bounds = header.getBoundingClientRect(), wrap = header.closest('.table-wrap').getBoundingClientRect();
      return bounds.left >= wrap.left && bounds.right <= wrap.right;
    }));
    assert.ok(positionBounds.every(Boolean), 'All position workload headers must remain visible.');
    const ranking = {...persian, title: 'رتبه‌بندی ساعات کارکنان آزمایشی',
      fields: [{id: 'employee_name', label: 'نام کامل کارمند', type: 'text'},
        {id: 'activity_hours', label: 'مجموع ساعات فعالیت', type: 'number', unit: 'ساعت'},
        {id: 'activity_count', label: 'تعداد فعالیت‌های ثبت‌شده', type: 'integer'},
        {id: 'average_activity_hours', label: 'میانگین ساعات هر فعالیت', type: 'number', unit: 'ساعت'}],
      rows: Array.from({length: 10}, (_, index) => [index < 2 ? 'نام آزمایشی مشترک' : `کارمند آزمایشی ${index + 1}`,
        123.456789 - index * 5, 71 + index, (123.456789 - index * 5) / (71 + index)]),
      provenance: {display_calendar: 'jalali', period_caption: '1405/04/19 تا 1405/07/19 (شمسی)',
        period_start: '2026-07-10', period_end_exclusive: '2026-10-12'}, truncated: true};
    await page.evaluate(data => renderReport(data), ranking);
    assert.equal(await page.locator('#table tbody tr').count(), 10);
    assert.deepEqual(await page.locator('#table th').allTextContents(),
      ['نام کامل کارمند', 'مجموع ساعات فعالیت (ساعت)', 'تعداد فعالیت‌های ثبت‌شده', 'میانگین ساعات هر فعالیت (ساعت)']);
    assert.deepEqual(await page.locator('#table tbody tr').first().locator('td').allTextContents(),
      ['نام آزمایشی مشترک', '۱۲۳٫۴۶', '۷۱', '۱٫۷۴']);
    assert.equal(ranking.rows[0][1], 123.456789);
    assert.equal(await page.locator('#warning').isVisible(), true);
    assert.match(await page.locator('#provenance').textContent(), /۱۴۰۵\/۰۴\/۱۹/);
    assert.equal(await page.evaluate(() => {
      const wrap = document.getElementById('table').getBoundingClientRect();
      return [...document.querySelectorAll('#table th')].every(cell => {
        const bounds = cell.getBoundingClientRect();
        return bounds.left >= wrap.left && bounds.right <= wrap.right;
      });
    }), true);
    ranking.rows = ranking.rows.slice(0, 6); ranking.truncated = false;
    await page.evaluate(data => renderReport(data), ranking);
    assert.equal(await page.locator('#table tbody tr').count(), 6);
    assert.equal(await page.locator('#warning').isVisible(), false);
    if (process.env.SAGEQL_RANKING_SCREENSHOT) await page.screenshot({path: process.env.SAGEQL_RANKING_SCREENSHOT, fullPage: true});
    const comparison = {...persian, title: 'تغییر مطلق و درصدی آزمایشی',
      fields: [{id: 'metric_label', label: 'شاخص', type: 'text'},
        {id: 'comparison_value', label: 'مرداد 1405', type: 'number'},
        {id: 'base_value', label: 'شهریور 1405', type: 'number'},
        {id: 'absolute_change', label: 'تغییر', type: 'number'},
        {id: 'percent_change', label: 'درصد تغییر', type: 'number', unit: '%'},
        {id: 'change_status', label: 'وضعیت تغییر', type: 'text'}],
      rows: [['ساعات (ساعت)', 20, 30, 10, '50.00000000000000000000001', 'افزایش'],
        ['تعداد', 40, 30, '-10', '-25', 'کاهش']],
      provenance: {...persian.provenance, comparison_start: '2026-07-23', comparison_end_exclusive: '2026-08-23'}, truncated: false};
    await page.evaluate(data => renderReport(data), comparison);
    assert.deepEqual(await page.locator('#table th').allTextContents(),
      ['شاخص', 'مرداد ۱۴۰۵', 'شهریور ۱۴۰۵', 'تغییر', 'درصد تغییر (%)', 'وضعیت تغییر']);
    assert.deepEqual(await page.locator('#table td').allTextContents(),
      ['ساعات (ساعت)', '۲۰', '۳۰', '۱۰', '۵۰', 'افزایش', 'تعداد', '۴۰', '۳۰', '-۱۰', '−۲۵', 'کاهش']);
    assert.equal(comparison.rows[0][4], '50.00000000000000000000001');
    assert.equal(await page.evaluate(() => displayPercent('2.345')), '۲٫۳۵');
    assert.equal(await page.evaluate(() => displayPercent('-0.00001')), '۰');
    assert.equal(await page.evaluate(() => displayPercent('1.23456E+2')), '۱۲۳٫۴۶');
    assert.equal(await page.evaluate(() => displayPercent('12345678901234567890.125')), '۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰٫۱۳');
    comparison.rows = [['ساعات (ساعت)', 0, 10, 10, null, 'مبنای صفر؛ درصد تعریف نمی‌شود']];
    await page.evaluate(data => renderReport(data), comparison);
    assert.equal(await page.locator('#table td').nth(4).textContent(), '—');
    assert.match(await page.locator('#table td').nth(5).textContent(), /مبنای صفر/);
    const decline = {...comparison, title: 'بیشترین افت ساعت آزمایشی',
      fields: [{id: 'employee_name', label: 'نام کامل کارمند', type: 'text'},
        {id: 'comparison_value', label: 'مرداد 1405', type: 'number', unit: 'ساعت'},
        {id: 'base_value', label: 'شهریور 1405', type: 'number', unit: 'ساعت'},
        {id: 'absolute_decrease', label: 'کاهش مطلق', type: 'number', unit: 'ساعت'},
        {id: 'percent_decrease', label: 'درصد افت', type: 'number', unit: '%'}],
      rows: [['نام مشترک', 100, 50, 50, '50.00000000000001'], ['نام مشترک', 40, 0, 40, '100']], truncated: false};
    await page.evaluate(data => renderReport(data), decline);
    assert.deepEqual(await page.locator('#table th').allTextContents(),
      ['نام کامل کارمند', 'مرداد ۱۴۰۵ (ساعت)', 'شهریور ۱۴۰۵ (ساعت)', 'کاهش مطلق (ساعت)', 'درصد افت (%)']);
    assert.deepEqual(await page.locator('#table td').allTextContents(),
      ['نام مشترک', '۱۰۰', '۵۰', '۵۰', '۵۰', 'نام مشترک', '۴۰', '۰', '۴۰', '۱۰۰']);
    assert.equal(decline.rows[0][4], '50.00000000000001');
    assert.equal(await page.evaluate(() => {
      const wrap = document.getElementById('table').getBoundingClientRect();
      return [...document.querySelectorAll('#table th')].every(cell => {
        const bounds = cell.getBoundingClientRect();
        return bounds.left >= wrap.left && bounds.right <= wrap.right;
      });
    }), true); // All decline columns, including the percent, fit at desktop width.
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
