"""Read-only measurements of deterministic reference and beta renders."""
import argparse,json,struct
from pathlib import Path
import numpy as np
from audio_metrics import rms_db,band_db,estimate_delay

def case_delay(original,processed,rate,name):
    if name.startswith('tone_'):
        # Remove the known periodic component only from delay estimation.
        # Central segments avoid startup/tail edges dominating the residual correlation.
        frequency=float(name.split('_')[1].replace('Hz',''))
        def residual(a):
            segment=a[4*rate:10*rate];spectrum=np.fft.rfft(segment)
            frequencies=np.fft.rfftfreq(len(segment),1/rate)
            spectrum[np.abs(frequencies-frequency)<100]=0
            return np.fft.irfft(spectrum,len(segment))
        return estimate_delay(residual(original),residual(processed),32768)
    return estimate_delay(original,processed,32768)

def read_wav(path):
    raw=path.read_bytes();pos=12;fmt=None;data=None
    while pos+8<=len(raw):
        tag=raw[pos:pos+4];size=struct.unpack_from('<I',raw,pos+4)[0];chunk=raw[pos+8:pos+8+size]
        if tag==b'fmt ':fmt=chunk
        if tag==b'data':data=chunk
        pos+=8+size+(size%2)
    code,channels,rate,_,_,bits=struct.unpack_from('<HHIIHH',fmt)
    if code==65534:code=struct.unpack_from('<H',fmt,24)[0]
    if code==3 and bits==32:x=np.frombuffer(data,dtype='<f4').astype(float)
    elif code==1 and bits==32:x=np.frombuffer(data,dtype='<i4').astype(float)/2147483648
    elif code==1 and bits==16:x=np.frombuffer(data,dtype='<i2').astype(float)/32768
    else:raise ValueError((path,code,bits))
    return rate,x.reshape(-1,channels)

def compare(base,profile,open_prefix='open'):
    rows=[]
    _,noise=read_wav(base.parent/'AutoDehiss-test-stimuli'/'white_-35dBFS.wav')
    _,cn=read_wav(base/f'cedar-realtime-{profile}'/'white_-35dBFS.wav')
    _,on=read_wav(base/f'{open_prefix}-{profile}'/'white_-35dBFS.wav')
    cedar_delay=estimate_delay(noise[:,0],cn[:,0],32768)
    open_delay=estimate_delay(noise[:,0],on[:,0],32768)
    for path in sorted((base/f'cedar-realtime-{profile}').glob('*.wav')):
        rate,c=read_wav(path);_,o=read_wav(base/f'{open_prefix}-{profile}'/path.name)
        _,x=read_wav(base.parent/'AutoDehiss-test-stimuli'/path.name)
        if x.shape[1]==1:x=np.repeat(x,2,axis=1)
        signal_present=bool(np.max(np.abs(x[:,0]))>0)
        case_c_delay=case_delay(x[:,0],c[:,0],rate,path.name) if signal_present else cedar_delay
        case_o_delay=case_delay(x[:,0],o[:,0],rate,path.name) if signal_present else open_delay
        n=len(x);c=c[case_c_delay:case_c_delay+n];o=o[case_o_delay:case_o_delay+n]
        if len(c)!=n or len(o)!=n:raise ValueError('Missing tail')
        row={'file':path.name,'measuredDelayCedar':case_c_delay if signal_present else None,
            'measuredDelayOpen':case_o_delay if signal_present else None,
            'silenceDelayFallback':not signal_present,
            'delayMethod':'residual correlation after tone notch in central segment' if path.name.startswith('tone_') else 'broadband correlation',
            'finite':bool(np.isfinite(c).all() and np.isfinite(o).all()),'channels':[]}
        for ch in range(2):
            a=x[3*rate:,ch];b=c[3*rate:,ch];d=o[3*rate:,ch]
            bands={}
            for lo,hi in [(20,800),(800,2000),(2000,5000),(5000,8000),(8000,12000),(12000,15000),(15000,24000)]:
                cb=band_db(b,rate,lo,hi);ob=band_db(d,rate,lo,hi)
                bands[f'{lo}-{hi}']={'cedarDbfs':cb,'openDbfs':ob,'openMinusCedarDb':ob-cb}
            row['channels'].append({'inputRmsDbfs':rms_db(a),'cedarRmsDbfs':rms_db(b),'openRmsDbfs':rms_db(d),
                'cedarReductionDb':rms_db(a)-rms_db(b),'openReductionDb':rms_db(a)-rms_db(d),
                'differenceRmsDbfs':rms_db(d-b),'cedarDryMaxError':float(np.max(np.abs(c[:,ch]-x[:,ch]))),
                'openDryMaxError':float(np.max(np.abs(o[:,ch]-x[:,ch]))),'bands':bands})
        if 'impulse' in path.name:
            row['unalignedPeakSamples']={'input':int(np.argmax(abs(x[:,0]))),'cedar':int(np.argmax(abs(read_wav(path)[1][:,0]))),'open':int(np.argmax(abs(read_wav(base/f'{open_prefix}-{profile}'/path.name)[1][:,0])))}
            row['impulseMetrics']={'inputPeak':float(np.max(np.abs(x[:,0]))),'cedarPeak':float(np.max(np.abs(c[:,0]))),
                'openPeak':float(np.max(np.abs(o[:,0]))),'cedarEnergy':float(np.sum(c[:,0]**2)),'openEnergy':float(np.sum(o[:,0]**2))}
        if 'noise_step' in path.name:
            row['noiseStepCurve']=[{'startSeconds':pos/rate,'inputDbfs':rms_db(x[pos:pos+rate//4,0]),
                'cedarDbfs':rms_db(c[pos:pos+rate//4,0]),'openDbfs':rms_db(o[pos:pos+rate//4,0])}
                for pos in range(0,n,rate//4)]
        rows.append(row)
    return {'profile':profile,'openPrefix':open_prefix,'sampleRate':48000,'blockSize':256,'declaredLatencyCedar':16128,
        'measuredDelayCedar':cedar_delay,'measuredDelayOpen':open_delay,
        'steadyAnalysisStartsSeconds':3,'highEndCut':0,'monoInputsDuplicatedToStereo':True,'results':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('profiles',nargs='*',default=['auto-0','auto--12','auto--26','manual--26'])
    parser.add_argument('--open-prefix',default='open')
    parser.add_argument('--output',type=Path,default=Path('outputs/equivalence-comparison.json'))
    args=parser.parse_args()
    base=Path('outputs/equivalence-renders')
    result=[compare(base,p,args.open_prefix) for p in args.profiles]
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    for profile in result:
        print(profile['profile'],len(profile['results']),'cases')
        for row in profile['results']:
            m=row['channels'][0]
            print(row['file'],'CEDAR reduction',round(m['cedarReductionDb'],3),'Open',round(m['openReductionDb'],3),'CEDAR dry error',m['cedarDryMaxError'])
