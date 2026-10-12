"""Audit time-local noise response from previously aligned reference renders.

This does not replace the stationary benchmark or measure perceptual quality.
The input comparator must already have aligned each render independently.
"""
import argparse
import json
from pathlib import Path


def audit(profiles, transition=6.0, window_tolerance=0.5):
    result = []
    for profile in profiles:
        for case in profile['results']:
            if 'noiseStepCurve' not in case:
                continue
            windows = []
            for point in case['noiseStepCurve']:
                t = point['startSeconds']
                if not transition <= t < transition + 2.0:
                    continue
                reference = point['inputDbfs'] - point['cedarDbfs']
                candidate = point['inputDbfs'] - point['openDbfs']
                difference = candidate - reference
                windows.append(dict(startSeconds=t, referenceReductionDb=reference,
                                    candidateReductionDb=candidate,
                                    differenceDb=difference,
                                    withinTolerance=abs(difference) <= window_tolerance))
            if not windows:
                raise ValueError('No windows cover the requested transition')
            result.append(dict(profile=profile['profile'], file=case['file'],
                               windows=windows,
                               passedWindows=sum(w['withinTolerance'] for w in windows),
                               totalWindows=len(windows)))
    if not result:
        raise ValueError('No time-local noise-step measurements found')
    return dict(scope='Diagnostic time-local RMS; not a perceptual equivalence score',
                transitionSeconds=transition, windowToleranceDb=window_tolerance,
                results=result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('comparison', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--transition', type=float, default=6.0)
    args = parser.parse_args()
    report = audit(json.loads(args.comparison.read_text(encoding='utf-8-sig')),
                   args.transition)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for case in report['results']:
        print(case['profile'], case['passedWindows'], '/', case['totalWindows'],
              'first-window difference dB:', case['windows'][0]['differenceDb'])
