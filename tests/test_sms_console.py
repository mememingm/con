import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sms_console import server


def numbers(count, device='3'):
    return [dict(number=f'TEST-{device}-{i}', device=device, ready=True, pool_id=device)
            for i in range(count)]


class SmsConsoleTests(unittest.TestCase):



    def test_imei_luhn_and_tac_statuses_are_explicit(self):
        self.assertTrue(server.imei_luhn('490154203237518'))
        self.assertFalse(server.imei_luhn('490154203237519'))
        self.assertFalse(server.imei_luhn('123'))
        with tempfile.TemporaryDirectory() as tmp:
            old = server.IMEI_DATA
            try:
                server.IMEI_DATA = Path(tmp) / 'imei-groups.json'
                server.write_json(server.IMEI_DATA, {'groups': [{'id': 'default', 'name': '短信测试设备'}], 'records': [
                    {'id': 'a', 'imei': '490154203237518', 'group_id': 'default'},
                    {'id': 'b', 'imei': '123', 'group_id': 'default'},
                    {'id': 'c', 'imei': '123', 'group_id': 'default'},
                ]})
                with patch.object(server, 'cached_numbers', return_value={'devices': []}):
                    rows = server.imei_records()
                self.assertEqual([r['format_status'] for r in rows], ['valid', 'invalid', 'duplicate'])
                self.assertEqual(rows[0]['model_status'], 'matched')
                self.assertEqual(rows[0]['source'], 'MoazEb/tac_full.csv')
            finally:
                server.IMEI_DATA = old

    def test_imei_model_lookup_returns_tac_and_explicit_invalid_status(self):
        matched = server.imei_model_lookup('490154203237518')
        self.assertEqual(matched['tac'], '49015420')
        self.assertEqual(matched['status'], 'matched')
        self.assertTrue(matched['source'])

        invalid = server.imei_model_lookup('123')
        self.assertEqual(invalid['status'], 'invalid')
        self.assertEqual(invalid['tac'], '')

    def test_batch_imei_lookup_returns_each_result_and_summary(self):
        class Capture:
            def err(self, code, message):
                return code, message

            def send(self, code, body, **kwargs):
                return code, body

        code, result = server.Handler.batch_imei_lookup(Capture(), {
            'imeis': ['490154203237518', '490154203237519', ' 490154203237518 ']
        })
        self.assertEqual(code, 200)
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['matched'], 2)
        self.assertEqual(result['valid'], 2)
        self.assertEqual(result['results'][1]['result']['status'], 'invalid')

    def test_batch_imei_lookup_rejects_empty_and_oversized_input(self):
        class Capture:
            def err(self, code, message):
                return code, message

            def send(self, code, body, **kwargs):
                return code, body

        capture = Capture()
        self.assertEqual(server.Handler.batch_imei_lookup(capture, {'imeis': []})[0], 400)
        self.assertEqual(server.Handler.batch_imei_lookup(capture, {'imeis': ['1'] * 501})[0], 400)

    def test_save_imei_results_persists_query_snapshot_and_deduplicates(self):
        class Capture:
            def err(self, code, message):
                return code, message

            def send(self, code, body, **kwargs):
                return code, body

        with tempfile.TemporaryDirectory() as tmp:
            old = server.IMEI_DATA
            try:
                server.IMEI_DATA = Path(tmp) / 'imei-groups.json'
                first = server.Handler.save_imei_results(Capture(), {
                    'imeis': ['490154203237518', '490154203237518', '123']
                })
                self.assertEqual(first[1]['added'], 2)
                self.assertEqual(first[1]['ignored'], 1)
                persisted = server.load_imei_groups()['records']
                self.assertEqual(len(persisted), 2)
                self.assertEqual(persisted[0]['query_result']['manufacturer'], 'Nokia')
                with patch.object(server, 'TAC_CATALOG', None):
                    reloaded = server.imei_records()
                self.assertEqual(reloaded[0]['brand'], 'Nokia')
                self.assertEqual(reloaded[1]['model_status'], 'invalid')
                self.assertEqual(reloaded[1]['imei'], '123')
                second = server.Handler.save_imei_results(Capture(), {'imeis': ['490154203237518']})
                self.assertEqual(second[1]['added'], 0)
                self.assertEqual(second[1]['records'][0]['id'], persisted[0]['id'])
                self.assertEqual(second[1]['records'][0]['created_at'], persisted[0]['created_at'])
                server.Handler.save_imei(Capture(), {'action': 'delete', 'ids': [persisted[0]['id']]})
                self.assertEqual([r['imei'] for r in server.load_imei_groups()['records']], ['123'])
            finally:
                server.IMEI_DATA = old

    def test_save_all_500_results_and_reject_bad_payloads_without_truncation(self):
        class Capture:
            def err(self, code, message):
                return code, message
            def send(self, code, body, **kwargs):
                return code, body

        with tempfile.TemporaryDirectory() as tmp, patch.object(server, 'IMEI_DATA', Path(tmp) / 'imei.json'):
            values = [f'{i:015d}' for i in range(500)]
            code, saved = server.Handler.save_imei_results(Capture(), {'imeis': values})
            self.assertEqual(code, 200)
            self.assertEqual(saved['added'], 500)
            self.assertEqual(len(server.load_imei_groups()['records']), 500)
            for payload in (None, [], {'imeis': []}, {'imeis': values + ['123']}, {'imeis': [123]}, {'imeis': ['x' * 101]}):
                self.assertEqual(server.Handler.save_imei_results(Capture(), payload)[0], 400)
                self.assertEqual(len(server.load_imei_groups()['records']), 500)

    def test_cached_imei_devices_include_pool_and_number_details(self):
        with patch.object(server, 'cached_numbers', return_value={
            'fetched_at': 123,
            'devices': [{
                'id': '3', 'name': 'EC20 3', 'imei': '490154203237518',
                'imeis': ['490154203237518'], 'online': True,
                'profile_count': 4, 'number_count': 1, 'ready_count': 1,
            }],
            'numbers': [{'device': '3', 'number': '+8613800000000', 'ready': True, 'line_id': 'l1'}],
        }):
            devices = server.cached_imei_devices()
        self.assertEqual(devices[0]['pool_id'], '3')
        self.assertEqual(devices[0]['numbers'][0]['number'], '+8613800000000')

    def test_imei_records_exactly_associate_cached_ec20(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = server.IMEI_DATA
            try:
                server.IMEI_DATA = Path(tmp) / 'imei-groups.json'
                server.write_json(server.IMEI_DATA, {'groups': [{'id': 'default', 'name': '默认'}], 'records': [
                    {'id': 'a', 'imei': '490154203237518', 'group_id': 'default'}]})
                with patch.object(server, 'cached_numbers', return_value={'devices': [
                    {'id': '3', 'name': 'EC20 3', 'imei': '490154203237518', 'online': True,
                     'number_count': 13, 'ready_count': 11}]}):
                    row = server.imei_records()[0]
                self.assertEqual(row['associated'], 'linked')
                self.assertEqual(row['devices'][0]['id'], '3')
                self.assertEqual(row['devices'][0]['ready_count'], 11)
            finally:
                server.IMEI_DATA = old

    def test_imei_api_group_import_limit_delete_persistence_and_conflict(self):
        class Capture:
            def err(self, code, message):
                return code, message

            def send(self, code, body, **kwargs):
                return code, body

        conflict_imei = '490154203237518'
        devices = [
            {'id': 'ec20-a', 'name': 'EC20 A', 'imei': conflict_imei, 'online': True,
             'number_count': 1, 'ready_count': 1},
            {'id': 'ec20-b', 'name': 'EC20 B', 'imei': conflict_imei, 'online': True,
             'number_count': 1, 'ready_count': 1},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            old = server.IMEI_DATA
            try:
                server.IMEI_DATA = Path(tmp) / 'imei-groups.json'
                server.write_json(server.IMEI_DATA, {
                    'groups': [{'id': 'default', 'name': '短信测试设备'}], 'records': []
                })
                capture = Capture()
                code, result = server.Handler.save_imei(capture, {
                    'action': 'create_group', 'name': 'API 验收组'
                })
                self.assertEqual(code, 200)
                group_id = next(g['id'] for g in result['groups'] if g['name'] == 'API 验收组')

                with patch.object(server, 'cached_numbers', return_value={'devices': devices}):
                    code, result = server.Handler.save_imei(capture, {
                        'action': 'import', 'group_id': group_id,
                        'imeis': [f'{i:015d}' for i in range(105)],
                    })
                    self.assertEqual(code, 200)
                    self.assertEqual(result['added'], 100)
                    self.assertEqual(len(result['records']), 100)

                    code, result = server.Handler.save_imei(capture, {
                        'action': 'import', 'group_id': group_id,
                        'imeis': [conflict_imei],
                    })
                    self.assertEqual(code, 200)
                    conflict = next(r for r in result['records'] if r['imei'] == conflict_imei)
                    self.assertEqual(conflict['associated'], 'conflict')
                    self.assertEqual(len(conflict['devices']), 2)

                    deleted_id = result['records'][0]['id']
                    code, result = server.Handler.save_imei(capture, {
                        'action': 'delete', 'ids': [deleted_id],
                    })
                    self.assertEqual(code, 200)
                    self.assertEqual(len(result['records']), 100)
                    persisted = server.load_imei_groups()
                    self.assertEqual(len(persisted['records']), 100)
                    self.assertNotIn(deleted_id, [r['id'] for r in persisted['records']])
            finally:
                server.IMEI_DATA = old

    def test_login_distinguishes_credentials_lockout_and_upstream_errors(self):
        class Capture:
            path = '/api/login'
            headers = {'X-Requested-With': 'sms-console'}
            def body(self):
                return dict(username='test', password='test-only')
            def err(self, code, message):
                return code, message
            def send(self, code, body, **kwargs):
                return code, body

        for upstream, expected in ((200, 200), (401, 401), (429, 429), (403, 502), (500, 502), (503, 502)):
            with self.subTest(upstream=upstream), \
                    patch.object(server.VoCatReader, '_open', return_value=(upstream, None)), \
                    patch.object(server, 'SESSIONS', {}):
                code, result = server.Handler.do_POST(Capture())
                self.assertEqual(code, expected)
                self.assertEqual(bool(server.SESSIONS), upstream == 200)
                if upstream != 200:
                    self.assertIn(f'HTTP {upstream}', result)
                if upstream == 429:
                    self.assertIn('限制登录', result)

    def test_odd_even_and_small_pools_cover_every_number_in_both_directions(self):
        for count in (2, 3, 4, 5, 13, 100):
            rows = numbers(count)
            for rounds in (1, 3, 5):
                with self.subTest(count=count, rounds=rounds):
                    plan = server.plan_pairs(rows, 'pairs', rounds, None)
                    per_round = ((count + 1) // 2) * 2
                    self.assertEqual(len(plan), per_round * rounds)
                    for r in range(rounds):
                        batch = plan[r * per_round:(r + 1) * per_round]
                        self.assertEqual({a['number'] for a, b in batch}, {n['number'] for n in rows})
                        self.assertEqual({b['number'] for a, b in batch}, {n['number'] for n in rows})
                        self.assertTrue(all(a['number'] != b['number'] for a, b in batch))
                        for i in range(0, per_round, 2):
                            self.assertEqual(batch[i], tuple(reversed(batch[i + 1])))

    def test_odd_extra_partner_rotates(self):
        rows = numbers(5)
        plan = server.plan_pairs(rows, 'pairs', 5, None)
        for r in range(5):
            batch = plan[r * 6:(r + 1) * 6]
            senders = [a['number'] for a, b in batch]
            self.assertEqual(senders.count(rows[r]['number']), 2)

    def test_single_number_never_sends_to_itself(self):
        for count in (0, 1):
            with self.assertRaises(ValueError):
                server.plan_pairs(numbers(count), 'pairs', 1, None)
        with self.assertRaises(ValueError):
            server.plan_pairs(numbers(1), 'pair', 1, numbers(1) * 2)

    def test_relay_keeps_expected_count_even_after_full_cycle(self):
        for count in (2, 3, 5):
            plan = server.plan_pairs(numbers(count), 'relay', 5, None)
            self.assertEqual(len(plan), count * 5)
            self.assertTrue(all(a['number'] != b['number'] for a, b in plan))

    def test_cross_pool_pairs_every_number_in_both_directions(self):
        left = numbers(3, 'left')
        right = numbers(1, 'right')
        plan = server.plan_pairs(left + right, 'cross_pool', 1, None, source=left, target=right)
        self.assertEqual(len(plan), 6)
        self.assertEqual({a['number'] for a, b in plan}, {n['number'] for n in left + right})
        self.assertEqual({b['number'] for a, b in plan}, {n['number'] for n in left + right})
        self.assertTrue(all(a['device'] != b['device'] for a, b in plan))

    def test_cache_groups_by_ec20_even_if_old_pool_metadata_conflicts(self):
        cached = dict(numbers=[dict(number='TEST', device='3', pool_id='old-group', pool_name='old')])
        with patch.object(server, 'read_json', return_value=cached):
            row = server.cached_numbers()['numbers'][0]
        self.assertEqual(row['pool_id'], '3')
        self.assertEqual(row['pool_name'], 'EC20 3')
        self.assertIsNone(row['slot_id'])

    def test_reader_preserves_all_device_lines_without_inventing_slots(self):
        reader = server.VoCatReader()
        lines = [dict(state=dict(phone_number=f'TEST-{i}', sms_ready=i % 2 == 0)) for i in range(13)]
        with patch.object(reader, 'get', side_effect=[(200, [dict(id=3, pool_id='wrong')]), (200, dict(state=dict(lines=lines)))]):
            rows = reader.numbers()
        self.assertEqual(len(rows), 13)
        self.assertTrue(all(n['pool_id'] == '3' and n['slot_id'] is None for n in rows))
        self.assertEqual(sum(n['ready'] for n in rows), 7)

    def test_reader_exposes_device_inventory_separately_from_number_rows(self):
        reader = server.VoCatReader()
        with patch.object(reader, 'get', side_effect=[
                (200, [dict(id=1, name='EC20 A'), dict(id=2, name='EC20 B', network_imei='IMEI-2')]),
                (200, dict(config=dict(profiles=[{}, {}]), state=dict(enabled=False, lines=[]))),
                (200, dict(config=dict(profiles=[{}]), state=dict(enabled=True, lines=[dict(state=dict(phone_number='B', sms_ready=True))]))),
        ]):
            rows = reader.numbers()
        self.assertEqual([d['profile_count'] for d in reader.devices], [2, 1])
        self.assertEqual(reader.devices[0]['number_count'], 0)
        self.assertEqual(reader.devices[1]['imei'], 'IMEI-2')
        self.assertEqual(rows[0]['pool_name'], 'EC20 B')
        self.assertEqual(rows[0]['imei'], 'IMEI-2')

    def test_device_read_failure_never_silently_drops_its_numbers(self):
        for status, error in ((401, PermissionError), (500, server.VoCatError)):
            reader = server.VoCatReader()
            with patch.object(reader, 'get', side_effect=[(200, [dict(id=3)]), (status, None)]):
                with self.assertRaises(error):
                    reader.numbers()

    def test_start_accepts_odd_pool_and_rejects_foreign_device(self):
        class Capture:
            def err(self, code, msg):
                return code, msg
            def send(self, code, body, **kwargs):
                return code, body
        rows = numbers(13)
        body = dict(mode='pairs', numbers=[n['number'] for n in rows], pool_id='3', rounds=2)
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, 'RUNS', Path(tmp)), \
                patch.object(server, 'current_run', return_value=None), \
                patch.object(server, 'cached_numbers', return_value=dict(numbers=rows + numbers(1, '2'))):
            code, result = server.Handler.start_run(Capture(), body, 'test')
            self.assertEqual(code, 200)
            self.assertEqual(result['summary']['overall']['planned'], 28)
            body['numbers'].append('TEST-2-0')
            self.assertEqual(server.Handler.start_run(Capture(), body, 'test')[0], 400)


if __name__ == '__main__':
    unittest.main()
