import unittest
from target80 import evaluate

def case(error,second=None,finite=True):
    channels=[{'inputRmsDbfs':-65,'cedarReductionDb':26,'openReductionDb':26-error}]
    if second is not None:channels.append({'inputRmsDbfs':-65,'cedarReductionDb':26,'openReductionDb':26-second})
    return {'file':'white.wav','finite':finite,'channels':channels}

class TargetTests(unittest.TestCase):
    def test_worst_stereo_channel_decides_single_case(self):
        r=evaluate([{'profile':'auto','results':[case(.1,.6)]}])
        self.assertEqual(r['totalCases'],1);self.assertEqual(r['passedCases'],0)
    def test_threshold_is_ceiling_and_nonfinite_output_fails(self):
        r=evaluate([{'profile':'auto','results':[case(.1),case(.1),case(.1),case(.1,finite=False)]}])
        self.assertEqual(r['requiredCases'],4);self.assertFalse(r['targetReached'])
    def test_empty_suite_does_not_pass(self):
        self.assertFalse(evaluate([])['targetReached'])
if __name__=='__main__':unittest.main(verbosity=2)
