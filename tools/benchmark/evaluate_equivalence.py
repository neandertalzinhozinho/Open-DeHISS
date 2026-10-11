"""A proposed functional criterion, not manufacturer certification."""
import json,sys
from pathlib import Path
data=json.loads(Path('outputs/equivalence-comparison.json').read_text(encoding='utf-8'))
checks=[]
for profile in data:
    for row in profile['results']:
        if row['file'] in ('silence.wav','isolated_impulse.wav'):continue
        for index,channel in enumerate(row['channels']):
            if channel['inputRmsDbfs']<-200:continue
            delta=abs(channel['cedarReductionDb']-channel['openReductionDb'])
            checks.append({'profile':profile['profile'],'file':row['file'],'channel':index,
                'metric':'steady RMS reduction difference','differenceDb':delta,'toleranceDb':0.5,'pass':delta<=0.5})
result={'criterion':'Proposed project criterion: reduction difference <=0.5dB; partial coverage only.',
    'passed':sum(c['pass'] for c in checks),'failed':sum(not c['pass'] for c in checks),'checks':checks}
Path('outputs/equivalence-criteria.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS',result['passed'],'FAIL',result['failed'],'(proposed steady RMS criterion only)')
sys.exit(1 if result['failed'] else 0)
