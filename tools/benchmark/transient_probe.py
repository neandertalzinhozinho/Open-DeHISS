"""Deterministic event preservation diagnostic for the independent prototype.

Difference of nonlinear outputs includes changes to underlying hiss. It is not
isolated residual noise, speech intelligibility or perceptual equivalence.
"""
import argparse,json
from pathlib import Path
import numpy as np
from recovered_kernel import render_experimental
from audio_metrics import rms_db
from voice_injection import write_wav

def run(root):
    root.mkdir(parents=True,exist_ok=False);fs=48000;n=fs*4
    rng=np.random.default_rng(20261013)
    noise=rng.normal(size=n);noise*=10**(-65/20)/np.sqrt(np.mean(noise**2))
    baseline,delay=render_experimental(noise,fs)
    write_wav(root/'noise-only.wav',noise[:,None],fs)
    rows=[]
    for kind,duration in [('fricative120ms',.12),('broadband20ms',.02),('baritone250ms',.25)]:
        length=int(fs*duration);time=np.arange(length)/fs
        if kind.startswith('baritone'):
            event=sum(np.sin(2*np.pi*120*k*time)/k for k in range(1,51))
        else:
            event=rng.normal(size=length)
            if kind.startswith('fricative'):
                z=np.fft.rfft(event);f=np.fft.rfftfreq(length,1/fs);z[(f<800)|(f>6000)]=0
                event=np.fft.irfft(z,length)
        event*=np.sin(np.pi*np.arange(length)/(length-1))**2
        event*=10**(-25/20)/np.sqrt(np.mean(event**2))
        clean=np.zeros(n);start=int(fs*1.5);clean[start:start+length]=event
        output,actual_delay=render_experimental(noise+clean,fs)
        difference=output-baseline;segment=difference[start:start+length]
        projection=float(np.dot(segment,event)/np.dot(event,event))
        rows.append({'event':kind,'latencySamples':actual_delay,'finite':bool(np.isfinite(output).all()),
                     'eventRmsLossDb':rms_db(event)-rms_db(segment),
                     'projectionGainDb':float(20*np.log10(max(abs(projection),1e-15))),
                     'relativeWaveformErrorDb':rms_db(segment-event)-rms_db(event),
                     'postEventDifferenceDbfs':rms_db(difference[start+length:start+length+fs//4])})
        write_wav(root/(kind+'-input.wav'),(noise+clean)[:,None],fs)
        write_wav(root/(kind+'-output.wav'),output[:,None],fs)
    report={'experimentalOnly':True,'seed':20261013,'baselineLatencySamples':delay,'cases':rows,
            'limitations':__doc__}
    (root/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);run(p.parse_args().output)
