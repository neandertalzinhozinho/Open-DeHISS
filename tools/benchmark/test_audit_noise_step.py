import unittest
from audit_noise_step import audit


class NoiseStepAuditTest(unittest.TestCase):
    def test_transition_window_excludes_startup_and_keeps_signed_difference(self):
        curve = [dict(startSeconds=t, inputDbfs=-45,
                      cedarDbfs=-57, openDbfs=-55)
                 for t in [0, 5.75, 6, 6.25, 7.75, 8]]
        report = audit([dict(profile='auto--12', results=[
            dict(file='noise_step.wav', noiseStepCurve=curve)])])
        row = report['results'][0]
        self.assertEqual(row['totalWindows'], 3)
        self.assertEqual(row['passedWindows'], 0)
        self.assertEqual(row['windows'][0]['differenceDb'], -2)
        self.assertEqual(row['windows'][0]['startSeconds'], 6)

    def test_tolerance_boundary_inclusive(self):
        curve = [dict(startSeconds=6, inputDbfs=-45,
                      cedarDbfs=-57, openDbfs=-57.5)]
        report = audit([dict(profile='auto--12', results=[
            dict(file='noise_step.wav', noiseStepCurve=curve)])])
        self.assertEqual(report['results'][0]['passedWindows'], 1)

    def test_missing_measurement_rejected(self):
        with self.assertRaises(ValueError):
            audit([dict(profile='auto--12', results=[])])


if __name__ == '__main__':
    unittest.main()
