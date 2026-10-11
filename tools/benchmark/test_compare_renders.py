import unittest,tempfile,struct
from pathlib import Path
import numpy as np
from compare_renders import read_wav,case_delay
from audio_metrics import estimate_delay

class RenderMetricsTests(unittest.TestCase):
    def test_float_wav_stereo_reader(self):
        samples=np.array([[.5,-.25],[0,1]],dtype='<f4')
        fmt=struct.pack('<HHIIHH',3,2,48000,384000,8,32)
        payload=samples.tobytes()
        body=b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(payload))+payload
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fixture.wav';path.write_bytes(b'RIFF'+struct.pack('<I',len(body))+body)
            rate,x=read_wav(path)
        self.assertEqual(rate,48000);np.testing.assert_array_equal(x,samples)
    def test_pcm_wav_reader(self):
        samples=np.array([[-16384,16384],[0,32767]],dtype='<i2')
        fmt=struct.pack('<HHIIHH',1,2,48000,192000,4,16)
        payload=samples.tobytes();body=b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(payload))+payload
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fixture.wav';path.write_bytes(b'RIFF'+struct.pack('<I',len(body))+body)
            _,x=read_wav(path)
        np.testing.assert_array_equal(x,samples.astype(float)/32768)
    def test_measured_alignment_beats_wrong_declared_latency(self):
        x=np.random.default_rng(11).normal(size=50000)
        processed=np.r_[np.zeros(1024),x,np.zeros(20000)]
        delay=estimate_delay(x,processed,32768)
        self.assertEqual(delay,1024)
        np.testing.assert_array_equal(x,processed[delay:delay+len(x)])
    def test_tone_delay_uses_residual_not_period_alias(self):
        rate=48000;n=rate*12;t=np.arange(n)/rate
        x=.05*np.sin(2*np.pi*1400*t)+np.random.default_rng(11).normal(size=n)*.0005
        y=np.r_[np.zeros(16128),x,np.zeros(rate*2)]
        self.assertEqual(case_delay(x,y,rate,'tone_1400Hz_plus_hiss.wav'),16128)

if __name__=='__main__':unittest.main(verbosity=2)
