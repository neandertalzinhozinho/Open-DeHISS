import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from prepare_blind_pilot import align_to_input, write_pcm24


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.audio = np.random.default_rng(17).normal(0, .1, (50000, 2))
        self.delay = 317
        self.processed = np.pad(self.audio * .2, ((self.delay, 400), (0, 0)))

    def test_alignment_preserves_gain_and_channels(self):
        aligned, delays = align_to_input(self.audio, self.processed, self.delay)
        self.assertEqual(delays, [self.delay, self.delay])
        np.testing.assert_array_equal(aligned, self.audio * .2)

    def test_missing_tail_rejected(self):
        with self.assertRaisesRegex(ValueError, 'tail'):
            align_to_input(self.audio, self.processed[:self.delay + len(self.audio) - 1], self.delay)

    def test_wrong_delay_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Delay'):
            align_to_input(self.audio, self.processed, 0)

    def test_nonfinite_and_channel_mismatch_rejected(self):
        broken = self.processed.copy()
        broken[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            align_to_input(self.audio, broken, self.delay)
        with self.assertRaisesRegex(ValueError, 'Channel'):
            align_to_input(self.audio, self.processed[:, :1], self.delay)

    def test_pcm24_roundtrip_preserves_quiet_audio(self):
        x = np.vstack([self.audio[:500] * .001, [[-1, 1], [0, 0]]])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'quiet.wav'
            write_pcm24(path, 48000, x)
            rate, decoded = wavfile.read(path)
            self.assertEqual(rate, 48000)
            np.testing.assert_allclose(decoded / 2147483648, x, rtol=0, atol=2e-7)

    def test_pcm24_rejects_clipping_instead_of_hiding_it(self):
        with self.assertRaises(ValueError):
            write_pcm24(Path('unused.wav'), 48000, np.array([[2.0, 0.0]]))


if __name__ == '__main__':
    unittest.main()
