"""Measure event loss after subtracting a separately rendered noise baseline."""
import argparse,json
from pathlib import Path
import numpy as np
from compare_renders import read_wav
from audio_metrics import rms_db,estimate_delay

EVENTS={'fricative120ms':.12,'broadband20ms':.02,'baritone250ms':.25}

def measure(inputs,renders,reference):
    rate,noise=read_wav(inputs/'noise-only.wav')
    _,processed_noise=read_wav(renders/'noise-only.wav')
    delay=estimate_delay(noise[:,0],processed_noise[:,0],32768)
    known={row['event']:row['cedarEventRmsLossDb'] for row in json.loads(reference.read_text())['cases']}
    rows=[]
    for event,duration in EVENTS.items():
        _,mixed=read_wav(inputs/(event+'-input.wav'))
        _,processed=read_wav(renders/(event+'-input.wav'))
        start=int(1.5*rate);length=int(duration*rate)
        clean=mixed[start:start+length,0]-noise[start:start+length,0]
        recovered=processed[start+delay:start+delay+length,0]-processed_noise[start+delay:start+delay+length,0]
        loss=rms_db(clean)-rms_db(recovered)
        rows.append({'event':event,'lossDb':loss,'cedarLossDb':known[event],
                     'additionalLossDb':loss-known[event],
                     'finite':bool(np.isfinite(recovered).all()),'delaySamples':delay})
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('renders',type=Path)
    p.add_argument('reference',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=measure(a.inputs,a.renders,a.reference)
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
