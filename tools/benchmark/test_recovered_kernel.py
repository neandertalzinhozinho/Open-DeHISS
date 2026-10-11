import unittest
import numpy as np
from recovered_kernel import curvature_energy,global_noise,ratio,spectral_smooth,noise_probability,gain,lookahead_hops
from recovered_kernel import BoundedTemporal,effective_curve,synthesize_transition
from recovered_kernel import render_experimental

class KernelTests(unittest.TestCase):
    def test_affine_spectrum_has_zero_interior_curvature(self):
        z=np.arange(33)*(1+2j)+3;np.testing.assert_allclose(curvature_energy(z)[1:-1],0)
    def test_noise_is_global_upper_median(self):
        self.assertEqual(global_noise([[1,100],[3,2]]),3)
    def test_energy_gain_cancels_in_probability_ratio(self):
        e=np.arange(1,34,dtype=float);np.testing.assert_allclose(ratio(e,2,1024,48000),ratio(e*100,200,1024,48000))
    def test_zero_spectral_memory_is_identity(self):
        f=np.linspace(-.9,.9,513);np.testing.assert_allclose(spectral_smooth(f,1024,48000,1),f,atol=1e-15)
    def test_probability_handles_silence_and_strong_signal_finitely(self):
        s=np.array([-1.,0.,1.]);h=noise_probability(s,s)
        self.assertTrue(np.isfinite(h).all());self.assertAlmostEqual(h[0],1);self.assertAlmostEqual(h[2],0)
    def test_gain_endpoints_and_frequency_profile(self):
        self.assertAlmostEqual(gain(0,np.array(9000.),-26),1)
        self.assertAlmostEqual(gain(1,np.array(9000.),-26),10**(-26/20))
    def test_lookahead_budget_stays_within_96ms(self):
        for fs,n in [(44100,1024),(48000,1024),(96000,2048)]:
            hop=n//2;count=lookahead_hops(fs,n,hop)
            self.assertLessEqual((n+count*hop)/fs,.096)
            self.assertGreater((n+(count+1)*hop)/fs,.096)
    def test_bounded_temporal_preserves_constant_during_startup_and_truncation(self):
        for tau in [1e-5,.25]:
            for available in [1,3,8,20]:
                filt=BoundedTemporal(1024,48000,tau)
                for _ in range(40):
                    np.testing.assert_allclose(filt.process(np.full((available,7),.6)),.6,atol=1e-14)
    def test_temporal_does_not_read_beyond_latency_budget(self):
        filt=BoundedTemporal(1024,48000,.25)
        frames=np.zeros((20,3));frames[8:]=1
        np.testing.assert_array_equal(filt.process(frames),0)
    def test_temporal_rejects_invalid_data_before_state_mutation(self):
        filt=BoundedTemporal(1024,48000,.25)
        with self.assertRaises(ValueError):filt.process([[np.nan]])
        self.assertIsNone(filt.state)
    def test_effective_curve_preserves_constant_gain_and_identity(self):
        rng=np.random.default_rng(20261011);signal=rng.normal(size=1024)
        z=np.fft.rfft(signal)
        for value in [0,.05,.5,1]:
            curve=np.full(513,value)
            np.testing.assert_allclose(effective_curve(curve),value,atol=1e-14)
            np.testing.assert_allclose(synthesize_transition(z,curve,curve),value*signal[256:768],atol=1e-14)
    def test_smoothing_reduces_alternating_bin_gain_ripple(self):
        curve=np.arange(513)%2
        self.assertLess(np.std(effective_curve(curve)),np.std(curve)*.1)
    def test_renderer_silence_and_zero_attenuation(self):
        rng=np.random.default_rng(7)
        for fs in [8000,44100,48000,96000]:
            x=rng.normal(size=2500)*.01
            out,delay=render_experimental(x,fs,0)
            np.testing.assert_array_equal(out,x);self.assertLessEqual(delay/fs,.096)
            out,delay=render_experimental(np.zeros(2500),fs)
            np.testing.assert_array_equal(out,0);self.assertLessEqual(delay/fs,.096)
if __name__=='__main__':unittest.main(verbosity=2)
