"""Fixed technical magnitude agreement; ignores phase, NOT perception."""
import argparse,json,re
from pathlib import Path
import numpy as np
from scipy.signal import stft
from compare_renders import read_wav
from prepare_blind_pilot import KINDS,align_to_input,digest
from audio_metrics import rms_db

def agreement(reference,candidate,rate):
    reference=np.asarray(reference);candidate=np.asarray(candidate)
    if reference.shape!=candidate.shape or reference.ndim!=2 or reference.shape[0]<2048 or reference.shape[1]<1 or not np.isfinite(reference).all() or not np.isfinite(candidate).all():
        raise ValueError('Need equal finite frames/channels, at least 2048 frames')
    if not isinstance(rate,(int,np.integer)) or isinstance(rate,bool) or rate<12000:
        raise ValueError('Need integer sample rate with Nyquist at least 6000 Hz')
    channels=[]
    for ch in range(reference.shape[1]):
        f,t,a=stft(reference[:,ch],rate,nperseg=2048,noverlap=1024,boundary=None,padded=False)
        _,_,b=stft(candidate[:,ch],rate,nperseg=2048,noverlap=1024,boundary=None,padded=False)
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError('Nonfinite analysis spectrum')
        ad=20*np.log10(np.maximum(np.abs(a),1e-15));bd=20*np.log10(np.maximum(np.abs(b),1e-15))
        valid=(f[:,None]>=800)&(f[:,None]<=6000)&(ad>-100)
        if not valid.any(): raise ValueError('No reference cells above analysis floor')
        error=np.abs(ad-bd)[valid]
        channels.append({'matchedCells':int(np.sum(error<=1)), 'eligibleCells':len(error),
                         'agreementPercent':float(100*np.mean(error<=1)),
                         'medianAbsoluteSpectralErrorDb':float(np.median(error)),
                         'p95AbsoluteSpectralErrorDb':float(np.quantile(error,.95)),
                         'outputLevelDifferenceDb':rms_db(candidate[:,ch])-rms_db(reference[:,ch])})
    return {'channels':channels,'worstChannelAgreementPercent':min(c['agreementPercent'] for c in channels)}

def _checked_hash(path,expected,label):
    path=Path(path)
    if not path.is_file(): raise ValueError(f'Missing {label}: {path}')
    if not isinstance(expected,str) or not re.fullmatch('[0-9a-fA-F]{64}',expected):
        raise ValueError(f'Missing or invalid {label} hash')
    if digest(path)!=expected.lower(): raise ValueError(f'{label} changed since render evidence capture')

def _render_records(log,role):
    if len(re.findall(r'^PASS renders=4\s*$',log,re.M))!=1:
        raise ValueError('Incomplete render evidence: need exactly PASS renders=4')
    matches=list(re.finditer(r'^RENDER (\S+\.wav) latency=(\d+) finite=1 frames=(\d+)\s*$',log,re.M))
    if len(matches)!=4 or {m[1] for m in matches}!=set(KINDS):
        raise ValueError('Incomplete render evidence: need all four unique finite renders')
    result={};previous=0
    for m in matches:
        values={}
        for name,normalized,text in re.findall(r'^FINAL (.+?) normalized=([^ ]+) text=(.*)$',log[previous:m.start()],re.M):
            try: value=float(normalized)
            except ValueError as exc: raise ValueError('Invalid final parameter value') from exc
            if not np.isfinite(value): raise ValueError('Nonfinite final parameter value')
            if name in values and values[name][0]!=value: raise ValueError('Conflicting final parameter values')
            values[name]=(value,text.strip())
        expected=({'Attenuation':(.35,'-26.00'),'Bias':(.8,'6.00'),
                   'Low Frequency Bias':(.5,'0.00'),'Automatic Threshold':(1,None),'Master Bypass':(0,None)}
                  if role=='cedar' else
                  {'Atenuacao (dB)':(.35,'-26.00'),'Bias (dB)':(.8,'6.00'),'LF Bias (dB)':(.5,'0.00'),
                   'Automatico':(1,None),'Bypass':(0,None),'Mix (%)':(1,'100.00'),'High End Cut (dB)':(1,'0.00')})
        for name,(value,text) in expected.items():
            actual=values.get(name)
            if actual is None or abs(actual[0]-value)>1e-5 or (text is not None and actual[1]!=text):
                raise ValueError(f'Missing/mismatched final parameter: {role} {name}')
        result[m[1]]={'latency':int(m[2]),'frames':int(m[3]),'parameters':values};previous=m.end()
    return result

def evaluate(root):
    root=Path(root).resolve()
    protocol=json.loads((root/'objective-protocol.json').read_text(encoding='utf-8'))
    if protocol.get('attenuationDb')!=-26 or protocol.get('biasDb')!=6 or protocol.get('auto') is not True:
        raise ValueError('Protocol settings differ from fixed objective09 protocol')
    evidence_path=root/'render-evidence.json'
    if not evidence_path.is_file(): raise ValueError('Missing render-evidence.json: pre-render provenance is required')
    evidence=json.loads(evidence_path.read_text(encoding='utf-8'));source=evidence['source']
    if source['sha256']!=protocol['sourceSha256']: raise ValueError('Source differs from protocol')
    _checked_hash(source['path'],source['sha256'],'source')
    source_rate,source_audio=read_wav(Path(source['path']))
    if not np.isfinite(source_audio).all(): raise ValueError('Nonfinite source audio')
    if {p.name for p in (root/'inputs').glob('*.wav')}!=set(KINDS): raise ValueError('Need exactly four predefined input conditions')
    if set(evidence['inputs'])!=set(KINDS): raise ValueError('Missing input hash records')
    records={}
    for role in ('open','cedar'):
        info=protocol['plugins'][role];ev=evidence['roles'][role]
        if (ev.get('capturedBeforeRender') is not True or ev['pluginSha256']!=info['sha256']
                or ev['pluginSha256After']!=ev['pluginSha256'] or ev['hostSha256After']!=ev['host']['sha256']):
            raise ValueError('Missing pre/post render binary evidence')
        _checked_hash(info['path'],info['sha256'],role+' plugin')
        _checked_hash(ev['host']['path'],ev['host']['sha256'],role+' host')
        command=ev['command']
        if (len(command)!=10 or Path(command[0]).resolve()!=Path(ev['host']['path']).resolve()
                or Path(command[1]).resolve()!=Path(info['path']).parents[2].resolve()
                or Path(command[2]).resolve()!=(root/'inputs').resolve()
                or Path(command[3]).resolve()!=(root/role).resolve()
                or command[4:] not in (['-26','1','-65','0','realtime','6'],['-26','1','-65','0','offline','6'])):
            raise ValueError('Render command differs from fixed protocol/paths')
        log_path=root/(role+'-host.log');_checked_hash(log_path,ev['logSha256'],role+' log')
        records[role]=_render_records(log_path.read_text(encoding='utf-8'),role)
        if {p.name for p in (root/role).glob('*.wav')}!=set(KINDS) or set(ev['renders'])!=set(KINDS):
            raise ValueError(f'Missing {role} reference/candidate renders')
    rows=[]
    for name in KINDS:
        path=root/'inputs'/name;_checked_hash(path,evidence['inputs'][name],'input '+name)
        rate,x=read_wav(path)
        if rate!=source_rate or x.shape!=source_audio.shape or not np.isfinite(x).all() or len(x)<int(1.5*rate)+2048:
            raise ValueError('Input shape/rate/finiteness/length mismatch')
        if name=='original.wav' and not np.array_equal(x,source_audio.astype(np.float32).astype(float)):
            raise ValueError('Original input differs from supplied source')
        outputs={};latencies={}
        for role in ('open','cedar'):
            render=root/role/name;_checked_hash(render,evidence['roles'][role]['renders'][name],role+' render')
            sr,y=read_wav(render);record=records[role][name]
            if sr!=rate or len(y)!=record['frames']: raise ValueError('Render rate/frame count mismatch')
            outputs[role],measured=align_to_input(x,y,record['latency']);latencies[role]=measured
        # Fixed predefined exclusion, not an assertion that this new recording has silence.
        result=agreement(outputs['cedar'][int(1.5*rate):],outputs['open'][int(1.5*rate):],rate)
        rows.append({'condition':name,'inputSha256':evidence['inputs'][name],'latencies':latencies,
                     'referenceSha256':digest(root/'cedar'/name),'candidateSha256':digest(root/'open'/name),**result})
    worst=min(r['worstChannelAgreementPercent'] for r in rows)
    return {'method':'objective STFT magnitude agreement within1dB','protocol':protocol,
            'renderEvidenceSha256':digest(evidence_path),'conditions':rows,
            'analysis':{'startSeconds':1.5,'frequencyHz':[800,6000],'referenceFloorDbfsExclusive':-100,
                        'maximumMagnitudeErrorDb':1,'window':'hann','nperseg':2048,'noverlap':1024,
                        'boundary':None,'padded':False,'independentGainNormalization':False},
            'worstConditionAndChannelPercent':worst,'requiredPercent':9,'technicalTargetReached':worst>=9,
            'perceptualEquivalenceEstablished':False,
            'limitations':'Technical criterion conditional on input and settings. Magnitudes ignore phase; an inverted signal scores 100%. No listener score, confidence in naturalness, or algorithm identity is inferred. Correlated STFT cells are not independent observations. Hashes audit captured artifacts, not cryptographic attestation of execution.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args()
    result=evaluate(a.root)
    with (a.root/'objective-result.json').open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2,allow_nan=False))
