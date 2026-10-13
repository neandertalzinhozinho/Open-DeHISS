"""Explore persistence of broadband-rise detection; never changes installed DSP."""
import argparse,json
from pathlib import Path
import numpy as np
from recovered_kernel import render_experimental
from compare_renders import read_wav
from audio_metrics import rms_db

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('outputs/beta07-prototype-rise-persistence-sweep.json'))
    parser.add_argument('--soft-takeover',action='store_true')
    args=parser.parse_args()
    fs, x = read_wav(Path('outputs/AutoDehiss-test-stimuli/noise_step_-65_to_-45.wav'))
    target = args.output
    if target.exists():
        raise SystemExit('Preserve existing experiment report')
    references = json.loads(Path('outputs/multires-r6-vst3-comparison.json').read_text())
    rows = []
    for attenuation in [-12, -26]:
        reference = next(p for p in references if p['profile'] == f'auto-{attenuation}')
        curve = next(c['noiseStepCurve'] for c in reference['results'] if 'noiseStepCurve' in c)
        candidates=[(.03,b) for b in [0,.25,.5,.75,1]] if args.soft_takeover else [(p,1.) for p in [.01,.02,.03,.05]]
        for persistence,first_blend in candidates:
            y, latency = render_experimental(x[:, 0], fs, attenuation=attenuation,
                slow_tau=.125, fast_width=1500, rapid_noise=True,
                rapid_persistence=persistence,rapid_first_blend=first_blend)
            windows = []
            for point in curve:
                t = point['startSeconds']
                if 6 <= t < 8:
                    segment = y[int(t*fs):int((t+.25)*fs)]
                    windows.append(dict(startSeconds=t,
                        differenceFromCedarDb=point['cedarDbfs']-rms_db(segment)))
            rows.append(dict(attenuationDb=attenuation, persistenceSeconds=persistence,firstFrameBlend=first_blend,
                latencyMs=latency/fs*1000, finite=bool(np.isfinite(y).all()),
                windows=windows))
            print(attenuation, persistence, windows[0]['differenceFromCedarDb'], flush=True)
    target.write_text(json.dumps(dict(scope='Exploratory single-path prototype; requires separate voice and VST3 validation', candidates=rows), indent=2))
