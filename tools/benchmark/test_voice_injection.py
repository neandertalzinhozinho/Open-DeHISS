import unittest,tempfile
from pathlib import Path
import numpy as np
from voice_injection import generate,write_wav
from compare_renders import read_wav
from audio_metrics import rms_db,band_db

class InjectionTests(unittest.TestCase):
    def test_known_added_hiss_level_and_band_without_changing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fs=48000;t=np.arange(fs*7)/fs
            original=(.03*np.sin(2*np.pi*120*t))[:,None]
            source=root/'source.wav';write_wav(source,original,fs)
            saved=source.read_bytes();generate(source,root/'test')
            _,originalRead=read_wav(root/'test/inputs/original.wav')
            _,injected=read_wav(root/'test/inputs/added_-55.wav')
            added=(injected-originalRead)[:,0]
            self.assertAlmostEqual(rms_db(added),-55,places=3)
            self.assertAlmostEqual(band_db(added,fs,800,6001),-55,places=3)
            self.assertLess(band_db(added,fs,20,750),-140)
            self.assertEqual(source.read_bytes(),saved)
            with self.assertRaises(FileExistsError):generate(source,root/'test')
    def test_reject_short_recording_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'short.wav';write_wav(source,np.zeros((48000,1)),48000)
            with self.assertRaises(ValueError):generate(source,root/'test')
            self.assertFalse((root/'test').exists())
if __name__=='__main__':unittest.main(verbosity=2)
