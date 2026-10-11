"""Measure response to known added hiss in a real recording, without capture.

Nonlinear difference includes changes to the original voice: it is NOT isolated
output noise or proof of perceptual quality. Inputs/outputs stay outside Git.
"""
import argparse,json,struct,subprocess,hashlib
from pathlib import Path
import numpy as np
from compare_renders import read_wav
from audio_metrics import rms_db,band_db,estimate_delay

def write_wav(path,x,rate):
    x=np.asarray(x,dtype='<f4');payload=x.tobytes();ch=x.shape[1]
    path.write_bytes(b'RIFF'+struct.pack('<I',36+len(payload))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,3,ch,rate,rate*ch*4,ch*4,32)+b'data'+struct.pack('<I',len(payload))+payload)

def generate(source,root):
    rate,x=read_wav(source)
    if rate<24000 or x.shape[1] not in (1,2) or len(x)/rate<6.1 or not np.isfinite(x).all():
        raise ValueError('Need finite mono/stereo recording >=6.1 seconds at >=24 kHz')
    root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    rng=np.random.default_rng(20261012)
    spectrum=np.fft.rfft(rng.normal(size=len(x)));freq=np.fft.rfftfreq(len(x),1/rate)
    spectrum[(freq<800)|(freq>6000)]=0
    noise=np.fft.irfft(spectrum,len(x));noise/=np.sqrt(np.mean(noise*noise))
    write_wav(inputs/'original.wav',x,rate)
    for level in [-65,-55]:write_wav(inputs/f'added_{level}.wav',x+noise[:,None]*10**(level/20),rate)
    stepped=noise*np.where(np.arange(len(x))/rate<5,10**(-65/20),10**(-45/20))
    write_wav(inputs/'added_step.wav',x+stepped[:,None],rate)
    (root/'manifest.json').write_text(json.dumps({'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'seed':20261012,'addedBandHz':[800,6000],'sampleRate':rate,'privateRecording':True},indent=2),encoding='utf-8')

def render(plugin,host,root,label,realtime,bias):
    dest=root/label
    p=subprocess.run([host,plugin,str(root/'inputs'),str(dest),'-26','1','-65','0','realtime' if realtime else 'offline',str(bias)],capture_output=True,text=True)
    (root/f'{label}-host.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError('VST3 host failed')

def measure(root,label):
    rate,x=read_wav(root/'inputs/original.wav');_,base=read_wav(root/label/'original.wav')
    delay=estimate_delay(x[:,0],base[:,0],32768);base=base[delay:delay+len(x)]
    results=[]
    for filename in ['added_-65.wav','added_-55.wav','added_step.wav']:
        _,mixed=read_wav(root/'inputs'/filename);_,out=read_wav(root/label/filename)
        ownDelay=estimate_delay(mixed[:,0],out[:,0],32768);out=out[ownDelay:ownDelay+len(x)]
        if len(base)!=len(x) or len(out)!=len(x):raise ValueError('Missing tail or alignment failure')
        difference=out-base;added=mixed-x
        # Speech/gestures start at ~1.5 s in this supplied recording.
        sections=[('active',1.5,min(9.5,len(x)/rate)),('post_step',6,min(9.5,len(x)/rate))]
        row={'input':filename,'delay':ownDelay,'finite':bool(np.isfinite(out).all()),'segments':{}}
        for section,start,end in sections:
            a=added[int(start*rate):int(end*rate),0];d=difference[int(start*rate):int(end*rate),0]
            row['segments'][section]={'addedInputRmsDbfs':rms_db(a),'outputDifferenceRmsDbfs':rms_db(d),'differenceReductionDb':rms_db(a)-rms_db(d),'difference800to6000ReductionDb':band_db(a,rate,800,6000)-band_db(d,rate,800,6000),'includesNonlinearChangesToVoice':True}
        results.append(row)
    result={'label':label,'baseDelay':delay,'attenuationDb':-26,'results':results,'limitations':'Output difference includes added-noise response AND nonlinear changes to original voice. Not an isolated noise measure or perceptual equivalence.'}
    (root/f'{label}-measurements.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--source',type=Path);p.add_argument('--plugin');p.add_argument('--host');p.add_argument('--label');p.add_argument('--realtime',action='store_true');p.add_argument('--bias',type=float,default=0);a=p.parse_args()
    if a.source:generate(a.source,a.root)
    if a.plugin:render(a.plugin,a.host,a.root,a.label,a.realtime,a.bias);measure(a.root,a.label)
