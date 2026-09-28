"""Local tests for the declarative MQ layer-1 runner: judge, fingerprints, repeat summary,
case-file validation. No MQTT connection."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mq_layer1 as m  # noqa: E402

CASE = {'id': 'T-50', 'layer': 1, 'action': 'phones.check', 'procedure': 'single', 'path': 'reject',
        'stability': 'deterministic', 'depends_on': [], 'expect': {'error.code': 'PHONE_NOT_FOUND',
                                                                   'error.certainty': ['not_started', 'known_failed']}}


def outcome(code='PHONE_NOT_FOUND', certainty='not_started', ids=('a',), complete=True):
    return {'observed': {'state': 'rejected', 'error.code': code, 'error.certainty': certainty, 'result.present': False},
            'task_ids': list(ids), 'complete': complete, 'evidence': {'final': {'id': ids[0], 'time': 'x'}}}


def record(case, out):
    j = m.judge(case, out)
    rec = {'id': case['id'], 'stability': case['stability'], 'verdict': j['verdict'], 'normalized': m.normalize(case, out)}
    rec['fingerprint'] = m.case_fingerprint(rec)
    return rec


def fake_run(i, recs, code='c1', env='e1'):
    return {'run_id': f'r{i}', 'meta': {'code_sha256': code}, 'environment_snapshot_id': env,
            'run_fingerprint': m.run_fingerprint(recs), 'cases': recs}


class JudgeTests(unittest.TestCase):
    def test_pass(self):
        j = m.judge(CASE, outcome())
        self.assertEqual(j['verdict'], 'pass')
        self.assertTrue(all(r.startswith('✓') for r in j['reasons']))

    def test_fail_names_the_missed_criterion(self):
        j = m.judge(CASE, outcome(code='TARGET_MISMATCH'))
        self.assertEqual(j['verdict'], 'fail')
        self.assertTrue(any(r.startswith('✗ error.code') for r in j['reasons']))

    def test_list_expect_means_membership(self):
        self.assertEqual(m.judge(CASE, outcome(certainty='known_failed'))['verdict'], 'pass')
        self.assertEqual(m.judge(CASE, outcome(certainty='unknown'))['verdict'], 'fail')

    def test_precondition_is_untested_not_failed(self):
        j = m.judge(CASE, {'precondition_failed': 'has_phone_row'})
        self.assertEqual(j['verdict'], 'untested')
        self.assertIn('has_phone_row', j['reasons'][0])

    def test_timeout_is_insufficient(self):
        self.assertEqual(m.judge(CASE, outcome(complete=False))['verdict'], 'insufficient')

    def test_skipped_optional_is_untested(self):
        self.assertEqual(m.judge(CASE, {'skipped': '本次未启用'})['verdict'], 'untested')

    def test_verdict_cap_partial(self):
        case = dict(CASE, verdict_cap='partial')
        self.assertEqual(m.judge(case, outcome())['verdict'], 'partial')
        self.assertEqual(m.judge(case, outcome(code='X'))['verdict'], 'fail')

    def test_list_expect_against_list_actual_is_equality(self):
        case = dict(CASE, expect={'sources': ['hardware']})
        self.assertEqual(m.judge(case, {'observed': {'sources': ['hardware']}, 'complete': True})['verdict'], 'pass')
        self.assertEqual(m.judge(case, {'observed': {'sources': ['hardware', 'cache']}, 'complete': True})['verdict'], 'fail')


class FingerprintTests(unittest.TestCase):
    def test_volatile_differences_keep_fingerprint(self):
        a = record(CASE, outcome(ids=('11111111',)))
        b = record(CASE, outcome(ids=('22222222',)))
        self.assertEqual(a['fingerprint'], b['fingerprint'])

    def test_verdict_change_changes_fingerprint(self):
        self.assertNotEqual(record(CASE, outcome())['fingerprint'], record(CASE, outcome(code='X'))['fingerprint'])

    def test_unjudged_observations_stay_out_of_fingerprint(self):
        out = outcome()
        out['observed']['row_count_matches_env'] = False
        self.assertNotIn('row_count_matches_env', m.normalize(CASE, out))
        self.assertEqual(record(CASE, out)['fingerprint'], record(CASE, outcome())['fingerprint'])

    def test_volatile_fields_are_dropped(self):
        case = dict(CASE, volatile_fields=['error.code'])
        self.assertNotIn('error.code', m.normalize(case, outcome()))

    def test_run_fingerprint_ignores_environmental_cases(self):
        env_case = dict(CASE, id='T-42', stability='environmental')
        det = record(CASE, outcome())
        r1 = m.run_fingerprint([det, record(env_case, outcome())])
        r2 = m.run_fingerprint([det, record(env_case, outcome(code='OTHER'))])
        self.assertEqual(r1, r2)


class RepeatTests(unittest.TestCase):
    def test_all_stable(self):
        runs = [fake_run(i, [record(CASE, outcome(ids=(str(i),)))]) for i in range(5)]
        rep = m.summarize_repeat(runs)
        self.assertTrue(rep['same_code'] and rep['run_fingerprint_consistent'] and rep['environment_consistent'])
        self.assertEqual((rep['deterministic_stable'], rep['deterministic_total'], rep['flipped']), (1, 1, []))

    def test_flip_is_reported_with_changed_field(self):
        runs = [fake_run(i, [record(CASE, outcome(code='PHONE_NOT_FOUND' if i != 3 else 'INTERNAL_ERROR'))]) for i in range(5)]
        rep = m.summarize_repeat(runs)
        self.assertEqual(rep['flipped'], ['T-50'])
        self.assertFalse(rep['run_fingerprint_consistent'])
        self.assertEqual(rep['cases'][0]['changed_fields'], ['error.code'])
        self.assertEqual(rep['cases'][0]['verdicts'].count('fail'), 1)

    def test_mixed_code_versions_are_flagged(self):
        runs = [fake_run(0, [record(CASE, outcome())], code='c1'), fake_run(1, [record(CASE, outcome())], code='c2')]
        self.assertFalse(m.summarize_repeat(runs)['same_code'])

    def test_markdown_lists_every_case(self):
        runs = [fake_run(i, [record(CASE, outcome())]) for i in range(2)]
        md = m.repeat_markdown(m.summarize_repeat(runs), ['01', '02'])
        self.assertIn('| T-50 | deterministic | 通过×2 | 稳定 | — | — |', md)


class CaseFileTests(unittest.TestCase):
    def test_real_case_file_is_valid(self):
        cases = m.load_cases()
        self.assertEqual(m.validate_cases(cases), [])
        for c in cases:
            self.assertEqual(c.get('depends_on'), [], c['id'])
            self.assertIn(c['stability'], m.STABILITY)
            if 'target' in c:
                self.assertEqual(c['target']['binding_version'], 1, c['id'])

    def test_validation_catches_problems(self):
        bad = copy.deepcopy(CASE)
        bad.update(depends_on=['T-39'], stability='sometimes', target={'device': '1'})
        problems = ' '.join(m.validate_cases([bad, dict(CASE, procedure='nope')]))
        for word in ('depends_on', 'stability', 'binding_version', 'duplicate id', 'unknown procedure'):
            self.assertIn(word, problems)

    def test_template_resolution(self):
        ctx = m.Ctx(None, {})
        ctx.vars['row'] = {'device': '1', 'slot': '8605', 'phone': '+1959'}
        t = ctx.resolve({'device': '$row.device', 'phone': '$row.phone', 'slot': '$slot.slot', 'x': 1}, {'slot': '9999'})
        self.assertEqual(t, {'device': '1', 'phone': '+1959', 'slot': '9999', 'x': 1})
        self.assertEqual(len(ctx.resolve('$new_uuid')), 36)


class PaginateTests(unittest.TestCase):
    def test_paginate_observation(self):
        class FakeCtx:
            env = {'real': [1, 2, 3]}

            def paginate(self, action, params):
                row = lambda s, i: {'target': {'slot': s, 'iccid': i, 'phone': '+1'}, 'available': True,
                                    'tunnel_state': 'registered', 'reason': None}
                return ([('p1', {'state': 'succeeded', 'result': {'items': [row('A', '1'), row('B', '2')], 'complete': False,
                                                                   'cursor': 'c', 'source': 'hardware'}}),
                         ('p2', {'state': 'succeeded', 'result': {'items': [row('B', '3')], 'complete': True,
                                                                   'cursor': None, 'source': 'hardware'}})],
                        [row('A', '1'), row('B', '2'), row('B', '3')])
        out = m.PROCEDURES['paginate'](FakeCtx(), {'action': 'phones.list', 'observe_extra': ['double_count']})
        o = out['observed']
        self.assertTrue(o['all_succeeded'] and o['complete_last'] and o['mid_pages_ok'] and o['availability_consistent'])
        self.assertEqual((o['sources'], o['empty_rows'], o['row_count_matches_env'], o['double_count']),
                         (['hardware'], 0, True, 1))
        self.assertEqual(out['task_ids'], ['p1', 'p2'])


class RetransmissionTests(unittest.TestCase):
    def setUp(self):
        msg = lambda seq, state, result=None: {'id': 'x', 'seq': seq, 'state': state, 'result': result, 'error': None}
        self.msg = msg
        self.original = [msg(1, 'accepted'), msg(2, 'running'), msg(3, 'succeeded', {'a': 1})]

        class N:
            def __init__(s, msgs):
                s.msgs = msgs

            def since(s, cid, mono):
                return s.msgs

        class C:
            pass
        self.C, self.N = C, N

    def changed(self, window):
        ctx = self.C()
        ctx.n = self.N(self.original + window)
        return m._changed_states(ctx, 'x', self.original[-1], window)

    def test_full_faithful_retransmission_is_not_a_change(self):
        self.assertEqual(self.changed([dict(r) for r in self.original]), [])

    def test_new_seq_is_a_change(self):
        self.assertEqual(len(self.changed([self.msg(4, 'running')])), 1)

    def test_changed_content_is_a_change(self):
        self.assertEqual(len(self.changed([self.msg(3, 'failed')])), 1)
        self.assertEqual(len(self.changed([self.msg(3, 'succeeded', {'a': 2})])), 1)


class AttributionTests(unittest.TestCase):
    def run_(self, env='e', probe=True, err=None):
        return {'meta': {'code_sha256': 'a'}, 'environment_snapshot_id': env, 'preconditions': {'env_probe_ok': probe},
                'env_probe_errors': err, 'selected_targets': {}}

    def rec(self, fp, evidence=None):
        return {'id': 'X', 'verdict': 'pass' if fp == 'p' else 'fail', 'fingerprint': fp, 'evidence': evidence or {}}

    def test_code_change_first(self):
        runs = [self.run_(), dict(self.run_(), meta={'code_sha256': 'b'})]
        self.assertTrue(m.attribute(runs, [(0, self.rec('p')), (1, self.rec('f'))]).startswith('代码变更'))

    def test_per_run_causes(self):
        hw = {'first_error': {'message': 'esim: no eUICC (ISD-R) found'}}
        runs = [self.run_('x', False, [{'message': 'Profile 失败: logical channel'}]), self.run_(), self.run_(), self.run_()]
        items = [(1, self.rec('p')), (2, self.rec('p')), (3, self.rec('f', hw))]  # run 1 did not expand the case
        a = m.attribute(runs, items)
        self.assertIn('第 1 次环境探测失败（现场硬件偶发）', a)
        self.assertIn('第 4 次现场硬件偶发', a)
        self.assertNotIn('环境变化', a)

    def test_environment_change_only_for_the_deviant_run(self):
        runs = [self.run_(), self.run_(), self.run_('other')]
        a = m.attribute(runs, [(0, self.rec('p')), (1, self.rec('p')), (2, self.rec('f'))])
        self.assertEqual(a, '第 3 次环境变化')

    def test_case_only_in_probe_failed_run(self):
        runs = [self.run_('x', False), self.run_(), self.run_()]
        self.assertTrue(m.attribute(runs, [(0, self.rec('u'))]).startswith('仅在环境探测失败的第 1 次出现'))

    def test_undetermined(self):
        runs = [self.run_(), self.run_(), self.run_()]
        self.assertIn('待定', m.attribute(runs, [(0, self.rec('p')), (1, self.rec('p')), (2, self.rec('f'))]))

    def test_resummarize_roundtrip(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for i in (1, 2):
                p = Path(d) / f'{i:02d}'
                p.mkdir()
                run = fake_run(i, [record(CASE, outcome())])
                (p / 'results.json').write_text(json.dumps(run), 'utf-8')
            rep = m.resummarize(d)
            self.assertEqual((rep['runs'], rep['flipped']), (2, []))
            self.assertTrue((Path(d) / 'repeat_report.md').exists())


class InventoryPaginateTests(unittest.TestCase):
    def test_inventory_rows_without_target(self):
        class FakeCtx:
            env = {'real': []}

            def paginate(self, action, params):
                items = [{'device': '1', 'slot': 'A', 'profiles_complete': False}, {'device': '2', 'slot': 'B', 'profiles_complete': False}]
                return [('p1', {'state': 'succeeded', 'result': {'items': items, 'complete': True, 'cursor': None,
                                                                  'source': 'registry'}})], items
        o = m.PROCEDURES['paginate'](FakeCtx(), {'action': 'inventory.get'})['observed']
        self.assertTrue(o['all_succeeded'] and o['complete_last'])
        self.assertEqual((o['sources'], o['profiles_complete_values'], o['empty_rows']), (['registry'], [False], 0))


if __name__ == '__main__':
    unittest.main()
