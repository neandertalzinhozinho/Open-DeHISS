"""Synthetic baritone regression: measure hiss BETWEEN harmonics, not voice RMS.

Run from workspace root. No microphone capture or proprietary plugin required.
"""
import argparse,json,struct,subprocess,re
from pathlib import Path
import numpy as np
from compare_renders import read_wav

def write_wav(path,x,rate):
    payload=np.asarray(x,dtype='<f4').tobytes()
    path.write_bytes(b'RIFF'+struct.pack('<I',36+len(payload))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,3,1,rate,rate*4,4,32)+b'data'+struct.pack('<I',len(payload))+payload)

def residual_db(x,rate,f0):
    spectrum=np.fft.rfft(x);freq=np.fft.rfftfreq(len(x),1/rate)
    # Exclude only actual periodic partials, leaving noise near and between them.
    distance=np.abs(freq-f0*np.round(freq/f0))
    selected=(freq>=800)&(freq<=6000)&(distance>5)
    return float(10*np.log10(max(2*np.sum(abs(spectrum[selected])**2)/len(x)**2,1e-30)))

def main():
    p=argparse.ArgumentParser();p.add_argument('plugin');p.add_argument('host');p.add_argument('output');p.add_argument('--bias',type=float,default=0);a=p.parse_args()
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    inputs=root/'inputs';inputs.mkdir();rate=48000;t=np.arange(rate*6)/rate
    for f0 in [90,120,150]:
        rng=np.random.default_rng(20261011+f0);voice=np.zeros_like(t)
        for h in range(1,int(6000/f0)+1):
            freq=h*f0
            # Strong upper harmonics and broad formants are intentionally difficult.
            envelope=(.3+np.exp(-((freq-1100)/700)**2)+.6*np.exp(-((freq-2600)/1000)**2))/h
            voice+=.025*envelope*np.sin(2*np.pi*freq*t+h*.37)
        write_wav(inputs/f'baritone_{f0}.wav',voice+rng.normal(0,10**(-65/20),len(t)),rate)
    result=[]
    for attenuation in [-12,-26]:
        dest=root/f'renders{attenuation}'
        process=subprocess.run([a.host,a.plugin,str(inputs),str(dest),str(attenuation),'1','-65','0','offline',str(a.bias)],capture_output=True,text=True)
        (root/f'host{attenuation}.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
        if process.returncode:raise RuntimeError('VST3 host failed')
        for f0 in [90,120,150]:
            _,x=read_wav(inputs/f'baritone_{f0}.wav');_,y=read_wav(dest/f'baritone_{f0}.wav')
            match=re.search(r'RENDER '+re.escape(f'baritone_{f0}.wav')+r' latency=(\d+)',process.stdout)
            if not match:raise ValueError('Host did not report per-file latency')
            delay=int(match.group(1))
            clean=x[3*rate:6*rate,0];filtered=y[3*rate+delay:6*rate+delay,0]
            if len(clean)!=len(filtered):raise ValueError('Incomplete aligned tail')
            reduction=residual_db(clean,rate,f0)-residual_db(filtered,rate,f0)
            result.append({'f0Hz':f0,'biasDb':a.bias,'attenuationDb':attenuation,'reportedDelaySamples':delay,'interharmonicNoiseReduction800to6000Db':reduction,'finite':bool(np.isfinite(y).all())})
    (root/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    # Explicit minimum for this beta, not a claim of perceptual equivalence.
    if not all(r['finite'] and r['interharmonicNoiseReduction800to6000Db']>=(-r['attenuationDb']*.25) for r in result):
        raise SystemExit('FAIL: excessive protection leaves most interharmonic hiss intact')
if __name__=='__main__':main()
