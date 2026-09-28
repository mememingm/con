// Unit-level event/render regression tests. No browser, network or live data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const box = { innerHTML: '', addEventListener() {} };
const planBox = { innerHTML: '' };
const source = fs.readFileSync(path.join(__dirname, '../sms_console/static/app.js'), 'utf8');
const context = vm.createContext({ assert, box, planBox,
  document: { querySelector: sel => sel === '#run-form' ? box : sel === '#plan-preview' ? planBox : null },
  window: { addEventListener() {} },
});
// Exclude only the application bootstrap (which performs the login request).
vm.runInContext(source.slice(0, source.lastIndexOf('(async () => {')), context);
assert.match(source, /const imeiDisplay = deviceOrLine =>/, 'IMEI display helper exists');
assert.match(source, /function pageImei\(el\)/, 'VoCat IMEI page exists');
assert.match(source, /api\("\/api\/imei\/devices"\)/, 'IMEI page loads VoCat devices');
assert.match(source, /api\("\/api\/imei\/lookup\?imei=/, 'IMEI page looks up TAC model data');
assert.match(source, /搜索设备名、设备 ID 或 IMEI/, 'IMEI page has device search');
assert.match(source, /完整 IMEI/, 'IMEI page renders the complete IMEI');
assert.match(source, /型号识别结果/, 'IMEI page renders model results');
assert.ok(source.includes('id=\\\"imei-manual-form\\\"'), 'IMEI page has manual lookup form');
assert.ok(source.includes('id=\\\"imei-manual-value\\\"'), 'manual lookup accepts an IMEI');
assert.ok(source.includes('manualLookup = await api(\"/api/imei/lookup?imei='), 'manual lookup reuses TAC API');
assert.ok(source.includes('id=\\\"imei-batch-form\\\"'), 'IMEI page has batch lookup form');
assert.ok(source.includes('api(\"/api/imei/batch-lookup\"'), 'batch lookup uses batch API');
assert.ok(source.includes('data-act=\\\"imei-save-batch\\\"'), 'batch results can be saved');
assert.ok(source.includes('data-act=\\\"imei-delete-record\\\"'), 'saved records can be deleted');
vm.runInContext(`
assert.equal(imeiDisplay({ online: false, imei: '490154203237518' }), '离线');
assert.equal(imeiDisplay({ online: true, imei: '' }), '未读取');
assert.equal(imeiDisplay({ online: undefined, imei: '' }), '未上报');
assert.equal(imeiDisplay({ online: true, imei: '490154203237518' }), '490154203237518');
`, context);
vm.runInContext(`
S.numbers = ['1', '2', '3'].flatMap(device => Array.from({length: device === '2' ? 4 : 13}, (_, i) => ({
  device, device_name: '设备 ' + device, pool_id: 'old-group', imei: 'IMEI-' + device, number: device + '-' + i, ready: true
})));
S.numbersInfo = {fetched_at: 1};
F.mode = 'pairs';
drawForm(); bindForm();
assert.equal(poolList().length, 3);
assert.equal(planCount(pickedPartition()), 14);
F.scope = 'cross'; F.mode = 'cross_pool'; F.poolFrom = '1'; F.poolTo = '2';
assert.equal(planCount(pickedPartition()), 26);
F.sel = 'manual'; drawForm();
assert.ok(box.innerHTML.includes('A 号池'), 'cross-pool list labels A pool');
assert.ok(box.innerHTML.includes('B 号池'), 'cross-pool list labels B pool');
assert.ok(box.innerHTML.includes('pick-group-head'), 'cross-pool list is grouped');
F.scope = 'pool'; F.mode = 'pairs'; F.sel = 'all'; F.pool = '1';
assert.ok(box.innerHTML.includes('data-pool="3"'), 'pool card rendered');
assert.ok(box.innerHTML.includes('IMEI-1'), 'IMEI displayed on device card');
assert.ok(!box.innerHTML.includes('data-sel="device"'), 'no device selector');
assert.ok(!box.innerHTML.includes('data-sel="line"'), 'no line selector');
F.manual.add('1-0'); F.a = '1-0'; F.b = '1-1';
box.onclick({target: {closest: () => ({dataset: {pool: '2'}})}});
assert.equal(F.pool, '2');
assert.equal(F.manual.size, 0);
assert.equal(F.a, '');
assert.equal(planCount(pickedPartition()), 4);
assert.ok(planBox.innerHTML.includes('首轮自动配对'), 'pair preview rendered');
box.onclick({target: {closest: () => ({dataset: {pool: '3'}})}});
assert.equal(F.pool, '3', 'pool switch to 3');
assert.equal(planCount(pickedPartition()), 14);
assert.equal(pickedPartition().all.length, 13);
assert.ok(!box.innerHTML.includes('id="start" disabled'), 'start enabled');
assert.ok(planBox.innerHTML.includes('下一轮轮换起点'), 'rotation hint rendered');
F.sel = 'manual'; F.manual.add('3-0'); F.manual.add('3-1'); F.manual.add('3-2');
assert.equal(planCount(pickedPartition()), 4);
F.mode = 'pair'; F.a = '1-0'; F.b = '1-1';
assert.equal(planCount(pickedPartition()), 0);
F.a = '3-0'; F.b = '3-0';
assert.equal(planCount(pickedPartition()), 0);
F.b = '3-1';
assert.equal(planCount(pickedPartition()), 2);
drawForm();
assert.ok(!box.innerHTML.includes('value="1-0"'));
S.numbers = S.numbers.filter(n => n.device !== '3' || n.number === '3-0');
F.mode = 'pairs'; F.sel = 'all'; drawForm();
assert.equal(planCount(pickedPartition()), 0);
assert.ok(box.innerHTML.includes('至少选择 2 个就绪号码'));
`, context);
console.log('SMS UI regression: card switch, pool identity, odd/even counts, pair scope, single-number guard, IMEI manual lookup OK');

