import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from score_blind_similarity import score

class BlindSimilarityTests(unittest.TestCase):
    def test_normalized_threshold_and_hidden_controls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'key.json').write_text(json.dumps({'1':'reference','2':'anchor','3':'candidate'}))
            (root/'scores.json').write_text(json.dumps({'scores':{'1':90,'2':10,'3':30}}))
            result=score(root/'key.json',root/'scores.json')
            self.assertEqual(result['normalizedSimilarityPercent'],25)
            self.assertTrue(result['targetReached']);self.assertTrue(result['validScale'])
    def test_collapsed_listener_scale_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'key.json').write_text(json.dumps({'1':'reference','2':'anchor','3':'candidate'}))
            (root/'scores.json').write_text(json.dumps({'scores':{'1':55,'2':50,'3':100}}))
            result=score(root/'key.json',root/'scores.json')
            self.assertFalse(result['validScale'])

if __name__=='__main__':unittest.main(verbosity=2)
