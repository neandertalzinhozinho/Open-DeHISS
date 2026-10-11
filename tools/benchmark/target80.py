"""Fixed partial target: >=80% of CASES, not duplicated stereo channels.

Uses the pre-existing 0.5 dB steady RMS tolerance, no rounding or omitted failures.
This does not measure subjective/perceptual equivalence.
"""
import argparse,json,math
from pathlib import Path

def evaluate(profiles):
    cases=[]
    for profile in profiles:
        for row in profile['results']:
            if row['file'] in ('silence.wav','isolated_impulse.wav'):continue
            active=[c for c in row['channels'] if c['inputRmsDbfs']>-200]
            if not active:continue
            errors=[abs(c['cedarReductionDb']-c['openReductionDb']) for c in active]
            cases.append({'profile':profile['profile'],'file':row['file'],'maxDifferenceDb':max(errors),'pass':row['finite'] and all(math.isfinite(e) and e<=.5 for e in errors)})
    passed=sum(c['pass'] for c in cases);total=len(cases)
    return {'criterion':'Every active channel in a case must match steady RMS reduction within 0.5 dB. Silence and impulse excluded as previously defined.','scope':'Partial functional benchmark; NOT perceptual equivalence. DSP stability, voice and onset regressions must pass independently.','passedCases':passed,'totalCases':total,'requiredCases':math.ceil(.8*total),'fraction':passed/total if total else 0,'targetReached':total>0 and passed>=math.ceil(.8*total),'cases':cases}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('comparison',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=evaluate(json.loads(a.comparison.read_text(encoding='utf-8')))
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result['passedCases'],'/',result['totalCases'],'cases; target',result['requiredCases'],'; reached',result['targetReached'])
    raise SystemExit(0 if result['targetReached'] else 1)
