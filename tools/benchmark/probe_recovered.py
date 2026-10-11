"""Local-only diagnostic of experimental equations; does not rank equivalence."""
import argparse,json
from pathlib import Path
import numpy as np
from recovered_kernel import render_experimental
from compare_renders import read_wav
from audio_metrics import rms_db,band_db
from voice_injection import write_wav

def main():
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--bias',type=float,default=0)
    p.add_argument('--attenuation',type=float,default=-26)
    p.add_argument('--slow-tau',type=float,default=.25);p.add_argument('--fast-width',type=float,default=3000);p.add_argument('--rapid-noise',action='store_true');args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);rows=[]
    for path in sorted(args.inputs.glob('*.wav')):
        fs,x=read_wav(path);channels=[]
        for channel in x.T:
            out,delay=render_experimental(channel,fs,args.attenuation,args.bias,slow_tau=args.slow_tau,fast_width=args.fast_width,rapid_noise=args.rapid_noise);channels.append(out)
        y=np.stack(channels,axis=1);write_wav(args.output/path.name,y,fs)
        start=min(len(x)//4,int(1.5*fs));end=min(len(x),int(9.5*fs))
        a=x[start:end,0];b=y[start:end,0]
        rows.append({'case':path.name,'sampleRate':fs,'algorithmicLatencySamples':delay,
                     'latencyMs':1000*delay/fs,'finite':bool(np.isfinite(y).all()),
                     'alignedOutput':True,'rmsReductionDb':rms_db(a)-rms_db(b),
                     'band800to6000ReductionDb':band_db(a,fs,800,6000)-band_db(b,fs,800,6000)})
    (args.output/'results.json').write_text(json.dumps({'experimentalOnly':True,'bias':args.bias,'attenuation':args.attenuation,'slowTau':args.slow_tau,'fastWidth':args.fast_width,'rapidNoise':args.rapid_noise,
        'limitations':'Independent bounded adaptation. Energy loss on voice is not isolated noise removal. No equivalence claim.',
        'cases':rows},indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
