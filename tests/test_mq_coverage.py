"""Local tests for the MQ coverage view and evidence masking. No MQTT connection."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mq_coverage  # noqa: E402
from mq_layer1 import mask, mask_text  # noqa: E402

ID_A = '11111111-1111-4111-8111-111111111111'
ID_B = '22222222-2222-4222-8222-222222222222'
ID_C = '33333333-3333-4333-8333-333333333333'


def fake_run():
    return {
        'run_id': 'test-run', 'started': '2026-09-22 10:00:00', 'finished': '2026-09-22 10:01:00',
        'meta': {'broker': 'b:1883', 'client_id': 'tester', 'node': 'n'},
        'commands': [{'id': ID_A, 'action': 'node.describe'}, {'id': ID_B, 'action': 'phones.list'},
                     {'id': ID_C, 'action': 'foo.bar'}],
        'cases': [
            {'t': 'node.describe/success', 'verdict': 'pass', 'summary': 'ok', 'task_ids': [ID_A], 'time': 't'},
            {'t': 'T-01', 'verdict': 'pass', 'summary': 'replay', 'task_ids': [ID_A], 'time': 't'},
            {'t': 'T-56', 'verdict': 'pass', 'summary': 'abc rejected', 'task_ids': [ID_B], 'time': 't'},
            {'t': 'T-56', 'verdict': 'fail', 'summary': 'page_size=0 accepted', 'task_ids': [ID_B], 'time': 't'},
            {'t': 'T-47a', 'verdict': 'pass', 'summary': 'hardware', 'task_ids': [ID_B], 'time': 't'},
            {'t': 'T-47b', 'verdict': 'pass', 'summary': 'mode rejected', 'task_ids': [ID_B], 'time': 't'},
            {'t': 'T-42', 'verdict': 'partial', 'summary': 'consistent', 'task_ids': [ID_B], 'time': 't'},
            {'t': 'T-37', 'verdict': 'untested', 'summary': 'no empty slot', 'task_ids': [ID_B], 'time': 't'},
            {'t': 'T-55', 'verdict': 'pass', 'summary': 'unsupported', 'task_ids': [ID_C], 'time': 't'},
        ],
    }


class CoverageTests(unittest.TestCase):
    def test_every_catalog_item_has_a_layer(self):
        ids = [c['id'] for c in mq_coverage.load_catalog()['cases']]
        self.assertEqual(len(ids), 68)
        self.assertEqual(sorted(ids), sorted(mq_coverage.LAYER))

    def test_empty_run_is_all_untested_with_reasons(self):
        cov = mq_coverage.coverage(None)
        self.assertEqual(cov['counts'], {'通过': 0, '失败': 0, '未测': 68})
        self.assertTrue(all(r['reason'] for r in cov['rows']))

    def test_any_failed_record_fails_the_item(self):
        rows = {r['id']: r for r in mq_coverage.coverage(fake_run())['rows']}
        self.assertEqual(rows['T-56']['verdict'], '失败')
        self.assertEqual(rows['T-47']['verdict'], '通过')
        self.assertEqual(rows['T-42']['verdict'], '未测（部分观察）')
        self.assertEqual(rows['T-37']['verdict'], '未测')
        self.assertEqual(rows['T-01']['task_ids'], [ID_A])

    def test_counts_partial_as_untested(self):
        c = mq_coverage.coverage(fake_run())['counts']
        self.assertEqual(c['通过'], 3)   # T-01, T-47, T-55
        self.assertEqual(c['失败'], 1)   # T-56
        self.assertEqual(c['未测'], 64)

    def test_matrix_columns(self):
        m = {r['action']: r for r in mq_coverage.coverage(fake_run())['matrix']}
        self.assertEqual([e['id'] for e in m['node.describe']['success']], [ID_A])
        self.assertEqual([e['t'] for e in m['node.describe']['boundary']], ['T-01'])
        self.assertIn('T-47', [e['t'] for e in m['phones.list']['reject']])
        self.assertIn('失败', [e['verdict'] for e in m['phones.list']['reject']])
        self.assertEqual(m['phones.list']['boundary'][0]['t'], 'T-47')
        self.assertFalse(any(e['t'] == 'T-37' for e in m['phones.list']['boundary']))  # untested stays empty

    def test_unknown_action_only_in_extras(self):
        cov = mq_coverage.coverage(fake_run())
        self.assertEqual([e['action'] for e in cov['extras']], ['foo.bar'])
        self.assertNotIn('foo.bar', [r['action'] for r in cov['matrix']])

    def test_markdown_has_matrix_and_68_rows(self):
        md = mq_coverage.to_markdown(mq_coverage.coverage(fake_run()))
        self.assertEqual(sum(1 for line in md.splitlines() if line.startswith('| T-')), 68)
        self.assertEqual(sum(1 for line in md.splitlines() if line.startswith('| ') and line.split('|')[1].strip()
                             in mq_coverage.load_catalog()['actions']), 14)
        self.assertIn('通过 3、失败 1、未测 64', md)


class StableRunTests(unittest.TestCase):
    def test_picks_majority_fingerprint_among_clean_probes_and_fills_skipped(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / 'repeat-20260101-000000'
            specs = [('01', 'fpX', False), ('02', 'fpA', True), ('03', 'fpA', True), ('04', 'fpB', True)]
            for name, fp, ok in specs:
                p = base / name
                p.mkdir(parents=True)
                run = dict(fake_run(), run_id=name, run_fingerprint=fp, preconditions={'env_probe_ok': ok},
                           meta={'code_sha256': 'c' * 64})
                run['cases'] = run['cases'] + [{'t': 'T-43', 'id': 'T-43', 'verdict': 'untested', 'reasons': ['本次未启用（include_t43）'],
                                                'task_ids': [], 'time': 't', 'summary': ''}]
                (p / 'results.json').write_text(json.dumps(run), 'utf-8')
            (base / 'repeat_report.json').write_text('{}', 'utf-8')
            single = Path(d) / '20260101-010000-aaaaaa'
            single.mkdir()
            srun = dict(fake_run(), run_id='single', meta={'code_sha256': 'd' * 64})
            srun['cases'] = [{'t': 'T-43', 'id': 'T-43', 'verdict': 'pass', 'summary': 'expired', 'task_ids': [ID_B], 'time': 't'}]
            (single / 'results.json').write_text(json.dumps(srun), 'utf-8')
            old = mq_coverage.MQ_EVIDENCE
            mq_coverage.MQ_EVIDENCE = Path(d)
            try:
                run = mq_coverage.stable_run()
            finally:
                mq_coverage.MQ_EVIDENCE = old
            cs = run['conclusion_source']
            self.assertEqual((cs['run'], cs['agreeing_runs'], cs['run_fingerprint']), ('03', ['02', '03'], 'fpA'))
            t43 = [c for c in run['cases'] if c.get('id') == 'T-43'][0]
            self.assertEqual((t43['verdict'], t43['batch']), ('pass', 'single'))
            rows = {r['id']: r for r in mq_coverage.coverage(run)['rows']}
            self.assertIn('repeat-20260101-000000/03', rows['T-01']['batch'])
            self.assertIn('single（dddd', rows['T-43']['batch'])


class ExportTests(unittest.TestCase):
    def test_decide(self):
        import mq_export_numbers as ex
        ok = {'state': 'succeeded', 'available': True}
        bad = {'state': 'failed', 'available': None, 'error_code': 'INTERNAL_ERROR'}
        rows = [{'phone': '+1', 'module': 'A', 'stable_run_ok': True, 'checks': [ok, ok]},
                {'phone': '+2', 'module': 'B', 'stable_run_ok': True, 'checks': [ok]},
                {'phone': '+3', 'module': 'C', 'stable_run_ok': True, 'checks': [ok, bad]},
                {'phone': '+4', 'module': 'C', 'stable_run_ok': True, 'checks': [bad]},
                {'phone': '+5', 'module': 'A', 'stable_run_ok': False, 'checks': [ok]},
                {'phone': '+6', 'module': 'D', 'stable_run_ok': True, 'checks': []}]
        out = {r['phone']: r for r in ex.decide(rows, {'B': 2}, 20)}
        self.assertEqual(out['+1']['recommendation'], '首选')
        self.assertTrue(out['+2']['layer1_pass'] and '2/20' in out['+2']['recommendation'])
        self.assertTrue(out['+3']['layer1_pass'] and 'INTERNAL_ERROR' in out['+3']['recommendation'])
        self.assertEqual(out['+3']['live_checks'], '1/2')
        self.assertFalse(out['+4']['layer1_pass'])
        self.assertFalse(out['+5']['layer1_pass'])
        self.assertTrue(out['+6']['layer1_pass'])
        self.assertIn('实时复核失败 2 次', out['+3']['module_read_failures'])


class MaskTests(unittest.TestCase):
    def test_masks_imei_and_iccid_in_text_but_not_phones(self):
        text = '读取模块 860588048251857 的 Profile 失败；ICCID 89014103211118510720；号码 +19592269821 +447770000000'
        out = mask_text(text)
        self.assertNotIn('860588048251857', out)
        self.assertIn('8605*******1857', out)
        self.assertNotIn('89014103211118510720', out)
        self.assertIn('+19592269821', out)
        self.assertIn('+447770000000', out)

    def test_masks_inside_a_slot_record(self):
        out = mask({'result': {'slot': {'slot': '863958041001301', 'current_iccid': '8901240527194105030',
                                        'profiles': [{'iccid': '8901240527194105030', 'phone': '+14793919427'}]}}})
        rec = out['result']['slot']
        self.assertEqual(rec['slot'], '8639*******1301')
        self.assertNotIn('8901240527194105030', str(out))
        self.assertIn('+14793919427', str(out))
        self.assertEqual(mask(out), out)  # idempotent

    def test_masks_identity_keys(self):
        out = mask({'target': {'slot': '860588048251857', 'iccid': '89014103211118510720', 'phone': '+19592269821'}})
        self.assertEqual(out['target']['slot'], '8605*******1857')
        self.assertTrue(out['target']['iccid'].startswith('8901') and '*' in out['target']['iccid'])
        self.assertEqual(out['target']['phone'], '+19592269821')


if __name__ == '__main__':
    unittest.main()
