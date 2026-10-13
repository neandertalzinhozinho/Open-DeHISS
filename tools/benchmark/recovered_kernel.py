"""Independent experimental translation of evidence-backed DSP equations.

Not enabled in the VST3. No claim of complete recovery or perceptual equivalence.
Finite protection is our own; temporal alignment/synthesis still need validation.
"""
import numpy as np

def curvature_energy(z):
    z=np.asarray(z,dtype=np.complex128)
    d=z.copy();d[1:-1]-=(z[:-2]+z[2:])*.5
    d[0]=complex(z[0].real-z[1].real,z[0].imag)
    d[-1]=complex(z[-1].real-z[-2].real,z[-1].imag)
    return np.abs(d)**2

def global_noise(frames):
    values=np.asarray(frames,dtype=float).reshape(-1)
    if not len(values) or not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid energy history')
    return float(np.partition(values,len(values)//2)[len(values)//2])

def ratio(energy,noise,n,fs,bias=0,lf_bias=0):
    k=np.arange(len(energy));c=n*5000/fs;r=10**(lf_bias/10+2)
    a,b=(c,c*r) if r<=1 else (c/r,c)
    return (k+a)*np.asarray(energy)/((k+b)*(noise*10**(bias/10)+1e-100))

def spectral_smooth(f,n,fs,t):
    f=np.asarray(f,dtype=float);last=len(f)-1
    lam=np.exp(-fs/(n*t));s=(1-lam)/(1+lam);v=s*lam;state=0.
    for j in range(last,0,-1):state=lam*state+f[j]
    out=np.empty_like(f)
    for j in range(last):out[j]=v*state;state=lam*state+f[j]
    out[last]=v*state
    for j in range(last,-1,-1):state=lam*state+f[j];out[j]+=s*state
    return out

def noise_probability(s1,s2):
    # Stabilized mixture, mathematically equivalent for finite interior values.
    # Clamping near singular S=-1 and lower bound are OUR safety protections.
    s1=np.clip(s1,-1+1e-12,1);s2=np.clip(s2,-1+1e-12,1)
    logits=np.stack((5+100*s1,-5+100*s2,np.zeros_like(s1)))
    weights=np.exp(logits-np.max(logits,axis=0));weights/=weights.sum(axis=0)
    values=np.stack(((1-s1)/(1+s1),(1-s2)/(1+s2),np.ones_like(s1)))
    return np.clip(np.sum(weights*values,axis=0),0,1)

def gain(probability,frequencies,attenuation,curve=1.5):
    f=np.asarray(frequencies);profile=1.25*(f*f+81e6)/(f*f+4500*f+81e6)
    floor=10**(attenuation/20)*profile;x=1-np.asarray(probability)
    return floor+(1-floor)*(curve*x+(1-curve)*x*x)

def lookahead_hops(fs,n,hop):
    if n/fs>.096:raise ValueError('FFT alone exceeds latency budget')
    return max(0,int(np.floor((.096*fs-n)/hop)))

class BoundedTemporal:
    """Independent bounded lookahead adaptation; not the original 20-frame filter.

    Caller supplies current and available future T, in chronological order.
    Normalization compensates omitted future terms without additional latency.
    The mass accumulator also prevents zero initialization bias at startup.
    """
    def __init__(self,n,fs,tau):
        if n<=0 or fs<=0 or tau<=0:raise ValueError('Positive filter parameters required')
        self.alpha=float(np.exp(-n/(2*fs*tau)))
        self.future_limit=min(19,lookahead_hops(fs,n,n//2))
        self.state=None;self.mass=0.

    def process(self,frames):
        frames=np.asarray(frames,dtype=float)
        if frames.ndim!=2 or not len(frames) or not np.isfinite(frames).all():
            raise ValueError('Finite chronological frames required')
        if self.state is None:self.state=np.zeros(frames.shape[1])
        if self.state.shape!=(frames.shape[1],):raise ValueError('Bin count changed')
        self.state=self.alpha*self.state+frames[0]
        self.mass=self.alpha*self.mass+1
        count=min(len(frames)-1,self.future_limit)
        weights=self.alpha**np.arange(count)
        numerator=self.state+np.sum(frames[1:count+1]*weights[:,None],axis=0)
        return numerator/(self.mass+weights.sum())

def circular_impulse_window(n):
    if n<4 or n%4:raise ValueError('FFT length must be divisible by four')
    hop=n//2;hann=.5-.5*np.cos(2*np.pi*np.arange(hop)/hop)
    window=np.zeros(n);window[:n//4]=hann[hop//2:];window[-n//4:]=hann[:hop//2]
    return window

def effective_curve(curve):
    """Evidence-backed IFFT/window/FFT path, independently expressed with NumPy."""
    curve=np.asarray(curve,dtype=float);n=2*(len(curve)-1)
    if not np.isfinite(curve).all():raise ValueError('Finite gain required')
    return np.fft.rfft(np.fft.irfft(curve,n)*circular_impulse_window(n)).real

def synthesize_transition(spectrum,previous_curve,new_curve):
    """Old-to-new ramp derived from static helper direction; runtime unverified."""
    spectrum=np.asarray(spectrum,dtype=complex);n=2*(len(spectrum)-1);hop=n//2
    old=np.fft.irfft(spectrum*np.asarray(previous_curve),n)[n//4:3*n//4]
    new=np.fft.irfft(spectrum*effective_curve(new_curve),n)[n//4:3*n//4]
    ramp=np.arange(hop)/hop
    return (1-ramp)*old+ramp*new

def render_experimental(signal,fs,attenuation=-26,bias=0,lf_bias=0,slow_tau=.25,fast_width=3000,rapid_noise=False,rapid_persistence=.05,rapid_first_blend=1.):
    """Offline prototype of bounded derived equations, not shipped VST3 DSP.

    Causal global median and shortened anticipation intentionally differ from
    the observed long-history pipeline. Returned audio is aligned (no padding
    delay); latency is reported as the conservative streaming scheduling bound.
    """
    signal=np.asarray(signal,dtype=float)
    if signal.ndim!=1 or not np.isfinite(signal).all() or fs<8000:
        raise ValueError('Finite mono samples and supported sample rate required')
    n=4
    while fs/n>48.828125:n*=2
    hop=n//2;count=int(np.ceil(len(signal)/hop))
    ahead=lookahead_hops(fs,n,hop);latency=n+ahead*hop
    if attenuation==0:return signal.copy(),latency
    padded=np.pad(signal,(n//4,n+ahead*hop))
    spectra=[];transformed=[];history=[];rising=0;hold=0
    limit=min(int(n*24000/fs),n//2)
    for j in range(count+ahead):
        z=np.fft.rfft(padded[j*hop:j*hop+n]);e=curvature_energy(z)
        history.append(e[:limit]);history=history[-21:]
        noise=global_noise(history)
        if rapid_noise:
            # Independent adaptation: a narrow voiced spectrum should not lift
            # the global median. Require a persistent broadband median rise.
            current=global_noise([e[:limit]])
            rising=rising+1 if current>4*max(noise,1e-100) else 0
            rise_trigger=max(1,int(np.ceil(rapid_persistence*fs/hop)))
            if rising>=rise_trigger:hold=21
            if hold>0:
                recent=global_noise(history[-3:])
                confidence=rapid_first_blend if rising==rise_trigger else 1.
                noise=max(noise,noise+confidence*(recent-noise));hold-=1
        q=ratio(e,noise,n,fs,bias,lf_bias)
        t=1-2/(q+1)
        spectra.append(z);transformed.append(t)
    filters=[BoundedTemporal(n,fs,1e-5),BoundedTemporal(n,fs,slow_tau)]
    previous=np.ones(n//2+1);out=np.empty(count*hop)
    frequencies=np.fft.rfftfreq(n,1/fs)
    for j in range(count):
        pending=np.asarray(transformed[j:j+ahead+1])
        fast_temporal=filters[0].process(pending)
        # Exclusion is set before the spectral sweeps, as observed in 208070.
        fast_temporal[:int(n*2000/fs)]=0
        fast=spectral_smooth(fast_temporal,n,fs,fast_width)
        slow=spectral_smooth(filters[1].process(pending),n,fs,1)
        curve=gain(noise_probability(fast,slow),frequencies,attenuation)
        out[j*hop:(j+1)*hop]=synthesize_transition(spectra[j],previous,curve)
        previous=effective_curve(curve)
    if not np.isfinite(out).all():raise FloatingPointError('Nonfinite reconstruction')
    return out[:len(signal)],latency
