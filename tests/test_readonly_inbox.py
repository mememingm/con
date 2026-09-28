import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'probe'))
from mqttx_readonly import Inbox


class InboxTests(unittest.TestCase):
    def test_only_owned_replies_are_ack_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            box=Inbox(Path(d)/'test.sqlite')
            raw=json.dumps({'id':'own','seq':1,'state':'succeeded'})
            self.assertFalse(box.receive(raw))
            box.own({'id':'own'})
            self.assertFalse(box.receive(raw,retained=True))
            self.assertTrue(box.receive(raw))
            box.db.close()
            box=Inbox(Path(d)/'test.sqlite')
            self.assertEqual(box.terminal('own')['state'],'succeeded')
            self.assertEqual(box.db.execute('SELECT count(*) FROM ack_intents').fetchone()[0],1)
            box.db.close()

    def test_duplicates_conflicts_and_old_seq(self):
        with tempfile.TemporaryDirectory() as d:
            box=Inbox(Path(d)/'test.sqlite')
            box.own({'id':'own'})
            latest=json.dumps({'id':'own','seq':3,'state':'succeeded'})
            self.assertTrue(box.receive(latest))
            self.assertTrue(box.receive(latest))
            self.assertFalse(box.receive(json.dumps({'id':'own','seq':3,'state':'failed'})))
            self.assertTrue(box.receive(json.dumps({'id':'own','seq':2,'state':'running'})))
            self.assertEqual(box.terminal('own')['seq'],3)
            self.assertEqual(box.db.execute('SELECT count(*) FROM inbox').fetchone()[0],2)
            self.assertEqual(box.db.execute('SELECT count(*) FROM conflicts').fetchone()[0],1)
            box.db.close()


if __name__=='__main__':
    unittest.main()
