"""Independent latency-constrained temporal adaptation, not recovered defaults."""
import json,argparse
from pathlib import Path
import numpy as np
from recovered_kernel import render_experimental
from compare_renders import read_wav
from audio_metrics import rms_db

def run(root,report,width_sweep=False,rapid_noise=False):
    if report.exists():raise ValueError('Preserve previous report')
    rows=[]
    reference=json.loads((root/'cedar-event-comparison.json').read_text())['cases']
    candidates=[(.125,w) for w in [1000,1500,2000,3000]] if width_sweep else [(t,3000) for t in [.05,.075,.1,.15,.2,.25]]
    for tau,width in candidates:
        cases=[]
        for row in reference:
            name=row['event'];fs,x=read_wav(root/(name+'-input.wav'))
            duration={'fricative120ms':.12,'broadband20ms':.02,'baritone250ms':.25}[name]
            y,latency=render_experimental(x[:,0],fs,slow_tau=tau,fast_width=width,rapid_noise=rapid_noise)
            start=int(fs*1.5);end=start+int(fs*duration)
            loss=rms_db(x[start:end,0])-rms_db(y[start:end])
            cases.append({'event':name,'lossDb':loss,'differenceFromCedarDb':loss-row['cedarEventRmsLossDb'],
                          'finite':bool(np.isfinite(y).all()),'latencyMs':1000*latency/fs})
        rows.append({'tauSeconds':tau,'fastWidthHz':width,'cases':cases})
    report.write_text(json.dumps({'scope':'Exploratory calibration on three synthetic events; separate validation required.',
                                 'candidates':rows},indent=2),encoding='utf-8')
    for row in rows:print(row['tauSeconds'],row['fastWidthHz'],[round(c['differenceFromCedarDb'],3) for c in row['cases']])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('report',type=Path);p.add_argument('--width-sweep',action='store_true');p.add_argument('--rapid-noise',action='store_true');a=p.parse_args();run(a.root,a.report,a.width_sweep,a.rapid_noise)
