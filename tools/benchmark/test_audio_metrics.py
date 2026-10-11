import unittest
import numpy as np
from audio_metrics import rms_db,band_db,estimate_delay
class MetricsTests(unittest.TestCase):
 def test_rms_analytic_sine(self):
  x=.1*np.sin(2*np.pi*1400*np.arange(48000)/48000)
  self.assertAlmostEqual(rms_db(x),-23.01029995664,places=8)
 def test_band_power_equals_time_power(self):
  x=np.random.default_rng(20261011).normal(size=48000)
  self.assertAlmostEqual(band_db(x,48000,0,24001),rms_db(x),places=10)
 def test_hiss_band_attenuation(self):
  x=np.random.default_rng(11).normal(size=48000)*.001
  for lo,hi in [(800,2000),(8000,12000)]:
   self.assertAlmostEqual(band_db(x*10**(-12/20),48000,lo,hi)-band_db(x,48000,lo,hi),-12,places=10)
 def test_delay_both_signs(self):
  x=np.random.default_rng(10).normal(size=4096)
  y=np.pad(x,(317,0))[:len(x)]
  self.assertEqual(estimate_delay(x,y,1000),317)
  self.assertEqual(estimate_delay(y,x,1000),-317)
 def test_silence_finite(self):
  self.assertEqual(rms_db(np.zeros(128)),-300)
if __name__=='__main__': unittest.main(verbosity=2)
