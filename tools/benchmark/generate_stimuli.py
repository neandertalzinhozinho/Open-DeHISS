import sys,json,struct,hashlib
from pathlib import Path
import numpy as np
from audio_metrics import metrics
out=Path('outputs/AutoDehiss-test-stimuli');out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists(): raise SystemExit('Output manifest exists; refusing to overwrite stimuli.')
rate=48000;n=rate*12;t=np.arange(n)/rate;rng=np.random.default_rng(20261011)
noise=rng.normal(size=n);noise/=np.sqrt(np.mean(noise*noise))
def write_float_wav(path,x):
 x=np.asarray(x,dtype='<f4');x=x[:,None] if x.ndim==1 else x
 payload=x.tobytes();channels=x.shape[1]
 header=b'RIFF'+struct.pack('<I',36+len(payload))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,3,channels,rate,rate*channels*4,channels*4,32)+b'data'+struct.pack('<I',len(payload))
 path.write_bytes(header+payload)
cases={}
for level in [-80,-65,-50,-35]:cases[f'white_{level}dBFS']=noise*10**(level/20)
cases['noise_step_-65_to_-45']=noise*np.where(t<6,10**(-65/20),10**(-45/20))
for freq in [100,800,1400,4900,5100,11000]:cases[f'tone_{freq}Hz_plus_hiss']=.05*np.sin(2*np.pi*freq*t)+noise*10**(-65/20)
impulse=np.zeros(n);impulse[rate*2]=.5;cases['isolated_impulse']=impulse
cases['silence']=np.zeros(n)
cases['stereo_noise_left_only']=np.stack((noise*10**(-65/20),np.zeros(n)),axis=1)
cases['stereo_correlated']=np.stack((noise,noise),axis=1)*10**(-65/20)
cases['stereo_antiphase']=np.stack((noise,-noise),axis=1)*10**(-65/20)
manifest={'sampleRate':rate,'seconds':12,'seed':20261011,'format':'IEEE float32 WAV','processedWithCedar':False,'cases':[]}
for name,x in cases.items():
 p=out/(name+'.wav');write_float_wav(p,x)
 mono=x if x.ndim==1 else x[:,0]
 manifest['cases'].append({'name':name,'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'metricsLeft':metrics(mono,rate)})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(f'Generated {len(cases)} test inputs; no CEDAR output measured.')
