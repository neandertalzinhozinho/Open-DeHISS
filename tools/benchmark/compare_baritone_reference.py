"""Read retained synthetic baritone renders with per-file host latency alignment."""
import argparse,json,re
from pathlib import Path
import numpy as np
from compare_renders import read_wav
from baritone_residual import residual_db

def delay(log,name):
    match=re.search(r'RENDER '+re.escape(name)+r' latency=(\d+)',log)
    if not match:raise ValueError('Missing host latency')
    return int(match.group(1))

def harmonic_db(x,fs,f0):
    z=np.fft.rfft(x);f=np.fft.rfftfreq(len(x),1/fs)
    mask=(f>=f0)&(f<=6000)&(np.abs(f-f0*np.round(f/f0))<.1)
    return float(10*np.log10(max(2*np.sum(abs(z[mask])**2)/len(x)**2,1e-30)))

def run(root,reference,reference_log,report):
    if report.exists():raise ValueError('Preserve existing report')
    own_log=(root/'host-26.txt').read_text();ref_log=reference_log.read_text();rows=[]
    for f0 in [90,120,150]:
        name=f'baritone_{f0}.wav';fs,x=read_wav(root/'inputs'/name)
        _,c=read_wav(reference/name);_,o=read_wav(root/'renders-26'/name)
        dc=delay(ref_log,name);do=delay(own_log,name);a=x[3*fs:6*fs,0];c=c[3*fs+dc:6*fs+dc,0];o=o[3*fs+do:6*fs+do,0]
        if len(c)!=len(a) or len(o)!=len(a):raise ValueError('Missing aligned output')
        rows.append({'f0':f0,'cedarDelay':dc,'openDelay':do,'finite':bool(np.isfinite(c).all() and np.isfinite(o).all()),
                     'cedarInterharmonicReductionDb':residual_db(a,fs,f0)-residual_db(c,fs,f0),
                     'openInterharmonicReductionDb':residual_db(a,fs,f0)-residual_db(o,fs,f0),
                     'cedarHarmonicEnergyLossDb':harmonic_db(a,fs,f0)-harmonic_db(c,fs,f0),
                     'openHarmonicEnergyLossDb':harmonic_db(a,fs,f0)-harmonic_db(o,fs,f0)})
    report.write_text(json.dumps({'attenuation':-26,'bias':6,'alignment':'Per-file declared host latency; reference execution licensed realtime.',
                                 'limitations':'Synthetic stationary harmonics; interharmonic metric includes artifacts and is not a perceptual score.',
                                 'cases':rows},indent=2),encoding='utf-8');print(json.dumps(rows,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('reference',type=Path);p.add_argument('reference_log',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args();run(a.root,a.reference,a.reference_log,a.report)
