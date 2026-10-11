"""Offline measurements, independent of the proprietary plugin."""
import numpy as np

def rms_db(x):
    x=np.asarray(x,dtype=np.float64)
    return float(10*np.log10(max(np.mean(x*x),1e-30)))

def band_db(x,sample_rate,low,high):
    x=np.asarray(x,dtype=np.float64)
    if x.ndim>1: x=x[0]
    n=len(x)
    if n<2: raise ValueError('Insufficient samples')
    spec=np.fft.rfft(x)
    weights=np.full(len(spec),2.0);weights[0]=1
    if n%2==0: weights[-1]=1
    freq=np.fft.rfftfreq(n,1/sample_rate)
    selected=(freq>=low)&(freq<high)
    power=np.sum(np.abs(spec[selected])**2*weights[selected])/(n*n)
    return float(10*np.log10(max(power,1e-30)))

def estimate_delay(original,processed,max_delay=8192):
    a=np.asarray(original,dtype=np.float64).reshape(-1)
    b=np.asarray(processed,dtype=np.float64).reshape(-1)
    size=1<<(len(a)+len(b)-1).bit_length()
    corr=np.fft.irfft(np.fft.rfft(b,size)*np.conj(np.fft.rfft(a,size)),size)
    candidates=np.arange(-max_delay,max_delay+1)
    return int(candidates[np.argmax(np.abs(corr[candidates%size]))])

def metrics(x,sample_rate):
    return {'rmsDbfs':rms_db(x),'peakDbfs':float(20*np.log10(max(np.max(np.abs(x)),1e-15))),
            'bandsDbfs':{f'{low}-{high}Hz':band_db(x,sample_rate,low,high) for low,high in [(20,800),(800,2000),(2000,5000),(5000,8000),(8000,12000),(12000,20000)]}}
