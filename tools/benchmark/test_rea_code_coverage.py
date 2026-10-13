import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from audit_rea_code_coverage import OPERATIONS, audit

class ReaCoverageTests(unittest.TestCase):
    def test_declares_twenty_distinct_operations(self):
        self.assertGreaterEqual(len(OPERATIONS),20)
        self.assertEqual(len(OPERATIONS),len(set(OPERATIONS)))
    def test_missing_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ('RecoveredMath.h','RecoveredSynthesis.h','DerivedChannel.h','MultiResolutionChannel.h','Denoiser.h'):
                (root/name).write_text('int x;\n')
            result=audit(root,root)
            self.assertFalse(result['passed']);self.assertEqual(len(result['missingEvidence']),len(OPERATIONS))

if __name__=='__main__':unittest.main(verbosity=2)
