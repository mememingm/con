import json
import tempfile
import unittest
from pathlib import Path

from reporting import load_catalog, parse_source, audit_probe, render_report, validate_verdict

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('C:/Users/27792/Desktop/wiki/24-MQ接口测试清单.md')
EVIDENCE = ROOT / 'evidence/20260921-103246-afdf0c9d'


class ReportingTests(unittest.TestCase):
    def test_catalog_preserves_all_source_cases_and_matrix_order(self):
        source = parse_source(SOURCE)
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        self.assertEqual([c['id'] for c in catalog['cases']], [f'T-{i:02}' for i in range(1, 69)])
        self.assertEqual(catalog['actions'], source['actions'])
        self.assertEqual(len(catalog['actions']), 14)
        for actual, original in zip(catalog['cases'], source['cases']):
            self.assertEqual(actual['criterion'], original['criterion'])
            self.assertTrue(actual['preconditions'])
            self.assertTrue(actual['not_tested_reason'])

    def test_existing_probes_are_observations_not_t_case_passes(self):
        audit = audit_probe(EVIDENCE)
        self.assertTrue(audit['integrity_ok'])
        self.assertEqual(audit['states'], ['accepted', 'running', 'succeeded'])
        self.assertEqual(audit['ack_no_subscribers'], 3)
        self.assertFalse(audit['business_ack_verified'])
        self.assertEqual(audit['eligible_cases'], [])
        self.assertIn('NODE_TYPE_DIFFERENCE', audit['finding_codes'])

    def test_tampered_summary_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'trace.jsonl').write_bytes((EVIDENCE / 'trace.jsonl').read_bytes())
            result = json.loads((EVIDENCE / 'result.json').read_text('utf-8'))
            result['terminal']['seq'] = 999
            (target / 'result.json').write_text(json.dumps(result), encoding='utf-8')
            self.assertFalse(audit_probe(target)['integrity_ok'])

    def test_offline_report_has_exact_tables_without_historical_promotion(self):
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        report = render_report(catalog, [], 'offline-review-test')
        rows = [line for line in report.splitlines() if line.startswith('| T-')]
        self.assertEqual(len(rows), 68)
        self.assertTrue(all('| 未测 |' in row for row in rows))
        self.assertIn('| node.describe |  |  |  |', report)
        self.assertNotIn('afdf0c9d', report)
        self.assertIn('| 编号 | 结论（通过·失败·未测） | 任务 ID | 北京时间 | 关键回包字段 | 备注 |', report)

    def example_verdict(self):
        return {
            'case_id': 'T-56', 'action': 'node.describe', 'category': '拒绝路径',
            'verdict': '通过', 'task_id': '11111111-1111-4111-8111-111111111111',
            'batch_id': 'batch-test', 'environment': 'isolated-test', 'origin': 'live',
            'beijing_time': '2026-09-21 11:00:00', 'raw_ref': 'trace.jsonl:1',
            'raw_reply': {'id': '11111111-1111-4111-8111-111111111111', 'seq': 1,
                          'time': '2026-09-21 11:00:00', 'state': 'rejected',
                          'error': {'code': 'INVALID_ARGUMENT', 'certainty': 'not_started'}},
            'note': '本地构造记录，仅测试导出逻辑。', 'criterion_review': '输入错误参数，核对错误码及未执行证据。',
            'key_fields': 'state=rejected; error.code=INVALID_ARGUMENT',
        }

    def test_expected_rejection_counts_as_pass_not_failure(self):
        value = self.example_verdict()
        validate_verdict(value, 'batch-test', 'isolated-test')
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        text = render_report(catalog, [value], 'batch-test', 'isolated-test')
        self.assertIn('| T-56 | 通过 | ' + value['task_id'], text)
        self.assertNotIn(value['task_id'] + ' + INVALID_ARGUMENT', text)

    def test_failure_matrix_uses_real_error_code(self):
        value = self.example_verdict()
        value['verdict'] = '失败'
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        text = render_report(catalog, [value], 'batch-test', 'isolated-test')
        self.assertIn(value['task_id'] + ' + INVALID_ARGUMENT', text)

    def test_success_is_linked_to_one_action_only(self):
        value = self.example_verdict()
        value.update(case_id='T-48', action='inventory.get', category='成功路径')
        value['raw_reply'].update(state='succeeded', error=None,
                                  result={'source': 'registry', 'profiles_complete': False})
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        text = render_report(catalog, [value], 'batch-test', 'isolated-test')
        self.assertIn('| inventory.get | ' + value['task_id'] + ' |  |  |', text)
        self.assertIn('| node.describe |  |  |  |', text)

    def test_failure_without_node_code_does_not_invent_matrix_code(self):
        value = self.example_verdict()
        value['verdict'] = '失败'
        value['raw_reply']['error'] = None
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        text = render_report(catalog, [value], 'batch-test', 'isolated-test')
        self.assertIn('| node.describe |  |  |  |', text)
        self.assertIn('| T-56 | 失败 | ' + value['task_id'], text)
        self.assertIn('节点未返回错误码', text)

    def test_unknown_action_is_not_falsely_attributed_to_known_action(self):
        value = self.example_verdict()
        value.update(case_id='T-55', action='__unknown_action__')
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        text = render_report(catalog, [value], 'batch-test', 'isolated-test')
        self.assertEqual(text.count(value['task_id']), 1)

    def test_template_and_source_matrix_agree(self):
        catalog = load_catalog(ROOT / 'cases/catalog.json', SOURCE)
        template = (ROOT.parent / 'tasks/templates/mqtt-test-report-template.md').read_text('utf-8-sig')
        rows = [line.split('|')[1].strip() for line in template.splitlines() if line.startswith('| ')]
        self.assertEqual(rows[1:15], catalog['actions'])

    def test_ack_to_foreign_task_is_an_integrity_error(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            records = [json.loads(line) for line in (EVIDENCE / 'trace.jsonl').read_text('utf-8').splitlines()]
            next(r for r in records if r['kind'] == 'ack_intent')['payload']['items'][0]['id'] = 'foreign-task'
            (target / 'trace.jsonl').write_text('\n'.join(json.dumps(r) for r in records), encoding='utf-8')
            (target / 'result.json').write_bytes((EVIDENCE / 'result.json').read_bytes())
            self.assertFalse(audit_probe(target)['integrity_ok'])

    def test_synthetic_history_wrong_batch_or_environment_cannot_enter_report(self):
        for key, bad in [('origin', 'simulation'), ('origin', 'historical'),
                         ('batch_id', 'other-batch'), ('environment', 'other-node')]:
            with self.subTest(key=key, value=bad):
                value = self.example_verdict()
                value[key] = bad
                with self.assertRaises(ValueError):
                    validate_verdict(value, 'batch-test', 'isolated-test')

    def test_missing_or_unmatched_evidence_cannot_pass(self):
        for key in ['task_id', 'raw_reply', 'raw_ref', 'beijing_time', 'criterion_review']:
            value = self.example_verdict()
            value.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_verdict(value, 'batch-test', 'isolated-test')
        value = self.example_verdict()
        value['raw_reply']['id'] = 'unrelated'
        with self.assertRaises(ValueError):
            validate_verdict(value, 'batch-test', 'isolated-test')


if __name__ == '__main__':
    unittest.main()
