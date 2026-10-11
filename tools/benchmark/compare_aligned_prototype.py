"""Compare aligned prototype renders against retained licensed reference data."""
import argparse,json
from pathlib import Path
import numpy as np
from compare_renders import read_wav,case_delay
from audio_metrics import rms_db

def compare(inputs,reference,prototype):
    rows=[]
    for path in sorted(inputs.glob('*.wav')):
        fs,x=read_wav(path);rc,c=read_wav(reference/path.name);ro,o=read_wav(prototype/path.name)
        if rc!=fs or ro!=fs:raise ValueError('Sample rates differ')
        if x.shape[1]==1 and c.shape[1]==2:x=np.repeat(x,2,axis=1)
        if o.shape[1]==1 and x.shape[1]==2:o=np.repeat(o,2,axis=1)
        if o.shape!=x.shape:raise ValueError('Aligned prototype shape differs')
        if not np.isfinite(c).all() or not np.isfinite(o).all():raise ValueError('Invalid output')
        active=np.max(abs(x))>0
        delay=case_delay(x[:,0],c[:,0],fs,path.name) if active else 16128
        if delay<0:raise ValueError('Negative reference alignment')
        c=c[delay:delay+len(x)]
        if c.shape!=x.shape:raise ValueError('Reference tail missing')
        reductions=[]
        for ch in range(x.shape[1]):
            a=x[3*fs:,ch];b=c[3*fs:,ch];d=o[3*fs:,ch]
            if rms_db(a)<=-200:continue
            cr=rms_db(a)-rms_db(b);pr=rms_db(a)-rms_db(d)
            reductions.append({'channel':ch,'cedarReductionDb':cr,'prototypeReductionDb':pr,'differenceDb':pr-cr})
        row={'file':path.name,'referenceDelay':delay,'channels':reductions,
             'eligible':bool(reductions) and 'impulse' not in path.name and 'silence' not in path.name}
        if 'noise_step' in path.name:
            row['stepWindows']=[{'start':s,'cedarReductionDb':rms_db(x[int(s*fs):int((s+.25)*fs),0])-rms_db(c[int(s*fs):int((s+.25)*fs),0]),
                'prototypeReductionDb':rms_db(x[int(s*fs):int((s+.25)*fs),0])-rms_db(o[int(s*fs):int((s+.25)*fs),0])} for s in [6,6.25,6.5,6.75,7,8]]
        rows.append(row)
    eligible=[r for r in rows if r['eligible']]
    passed=sum(all(abs(c['differenceDb'])<=.5 for c in r['channels']) for r in eligible)
    return {'scope':'Experimental partial RMS criterion; not perceptual equivalence.',
            'referenceDirectory':str(reference),'prototypeDirectory':str(prototype),
            'passed':passed,'total':len(eligible),'cases':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('reference',type=Path)
    p.add_argument('prototype',type=Path);p.add_argument('report',type=Path);a=p.parse_args()
    result=compare(a.inputs,a.reference,a.prototype)
    if a.report.exists():raise ValueError('Preserve existing report')
    a.report.write_text(json.dumps(result,indent=2),encoding='utf-8');print(result['passed'], '/',result['total'])
