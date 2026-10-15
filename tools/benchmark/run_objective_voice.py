"""Fresh, auditable fixed objective09 renders. Never reuse or overwrite outputs.

This runner records artifacts before invoking the hosts and preserves a failed
attempt without creating a successful result. It does not establish perception.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

import numpy as np

from compare_renders import read_wav
from prepare_blind_pilot import KINDS, digest, plugin_info
from score_objective_voice import evaluate, _render_records
from voice_injection import generate

DEFAULT_OPEN = Path('C:/Program Files/Common Files/VST3/Open DeHISS.vst3')
DEFAULT_CEDAR = Path('C:/Program Files/Common Files/VST3/CEDARAutoDehiss.vst3')


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def host_environment(skip_state_snapshot):
    # Windows keys are case insensitive, but Python dictionaries may preserve
    # differently cased duplicates inherited from a parent environment.
    env = {key.upper(): value for key, value in os.environ.items()}
    env['OPEN_DEHISS_HOST_SKIP_STATE_SNAPSHOT'] = '1' if skip_state_snapshot else '0'
    return env


def check_unchanged(source, source_hash, root, inputs, host, host_hash, bundle, info):
    if digest(source) != source_hash:
        raise ValueError('Source changed during render preparation/execution')
    if {path.name for path in (root / 'inputs').glob('*.wav')} != set(KINDS):
        raise ValueError('Input set changed during render')
    if any(digest(root / 'inputs' / name) != inputs[name] for name in KINDS):
        raise ValueError('Input changed during render')
    if digest(host) != host_hash:
        raise ValueError('Host changed during render')
    if plugin_info(bundle) != info:
        raise ValueError('Plugin or module metadata changed during render')


def run(source, root, host, candidate=DEFAULT_OPEN, reference=DEFAULT_CEDAR,
        skip_state_snapshot=False):
    source, root, host = Path(source).resolve(), Path(root).resolve(), Path(host).resolve()
    bundles = {'open': Path(candidate).resolve(), 'cedar': Path(reference).resolve()}
    if root.exists():
        raise FileExistsError(f'Refusing to overwrite existing attempt: {root}')
    if not host.is_file():
        raise FileNotFoundError(host)
    source_hash, host_hash = digest(source), digest(host)
    plugins = {role: plugin_info(bundle) for role, bundle in bundles.items()}
    rate, signal = read_wav(source)
    # Native host emits stereo; keep source/input channels matched to the fixed
    # recording protocol, instead of silently duplicating a mono recording.
    if signal.ndim != 2 or signal.shape[1] != 2 or not np.isfinite(signal).all():
        raise ValueError('Objective09 requires a finite stereo source recording')
    duration = len(signal) / rate
    timeout = 4 * (duration + 3) + 60
    env = host_environment(skip_state_snapshot)
    safe_env = {'OPEN_DEHISS_HOST_SKIP_STATE_SNAPSHOT': env['OPEN_DEHISS_HOST_SKIP_STATE_SNAPSHOT']}
    created = False
    role = 'preparation'
    try:
        print(f'Preparing four fixed conditions from {duration:.6f}s source; root={root}', flush=True)
        generate(source, root)
        created = True
        input_hashes = {name: digest(root / 'inputs' / name) for name in KINDS}
        if digest(source) != source_hash:
            raise ValueError('Source changed during render preparation/execution')
        if json.loads((root / 'manifest.json').read_text(encoding='utf-8'))['sourceSha256'] != source_hash:
            raise ValueError('Generated manifest source hash differs from pre-generation capture')
        protocol = {'sourceSha256': source_hash, 'plugins': plugins,
                    'criterion': 'fraction of aligned STFT magnitude cells within1dB,800..6000Hz, reference above-100dBFS; target9percent',
                    'attenuationDb': -26, 'biasDb': 6, 'auto': True}
        write_new(root / 'objective-protocol.json', protocol)
        evidence = {'recordedAt': now(), 'source': {'path': str(source), 'sha256': source_hash},
                    'inputs': input_hashes, 'roles': {},
                    'environmentOverrides': safe_env, 'environmentKeyPolicy': 'case-insensitive keys deduplicated to uppercase',
                    'privateRecording': True, 'sampleRate': rate, 'sourceFrames': len(signal),
                    'parameters': {'attenuationDb': -26, 'auto': True, 'biasDb': 6,
                                   'lfBiasDb': 0, 'mixPercent': 100, 'highEndCutDb': 0},
                    'gainPolicy': 'No independent gain normalization', 'timeoutPerRoleSeconds': timeout}
        for role in ('open', 'cedar'):
            mode = 'offline' if role == 'open' else 'realtime'
            evidence['roles'][role] = {'host': {'path': str(host), 'sha256': host_hash},
                'pluginSha256': plugins[role]['sha256'],
                'command': [str(host), str(bundles[role]), str(root / 'inputs'), str(root / role),
                            '-26', '1', '-65', '0', mode, '6'],
                'capturedBeforeRender': True, 'environmentOverrides': safe_env}
        write_new(root / 'render-evidence-start.json', evidence)
        for role in ('open', 'cedar'):
            ev = evidence['roles'][role]
            check_unchanged(source, source_hash, root, input_hashes, host, host_hash, bundles[role], plugins[role])
            ev['startedAt'] = now()
            # Separate immutable pre-launch record for this role. The reference
            # is independently checked after the candidate run completes.
            write_new(root / f'{role}-evidence-start.json', ev)
            print(f'Rendering {role}: {ev["command"][8]}, timeout={timeout:.1f}s; log={role}-host.log', flush=True)
            log_path = root / f'{role}-host.log'
            with log_path.open('x', encoding='utf-8') as log:
                process = subprocess.run(ev['command'], stdout=log, stderr=subprocess.STDOUT,
                                         timeout=timeout, env=env,
                                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            ev['finishedAt'] = now()
            ev['returnCode'] = process.returncode
            ev['logSha256'] = digest(log_path)
            if process.returncode:
                raise RuntimeError(f'{role} host failed: exit {process.returncode}; see {log_path}')
            check_unchanged(source, source_hash, root, input_hashes, host, host_hash, bundles[role], plugins[role])
            _render_records(log_path.read_text(encoding='utf-8'), role)
            if {path.name for path in (root / role).glob('*.wav')} != set(KINDS):
                raise ValueError(f'{role}: incomplete four-render output set')
            ev['hostSha256After'] = digest(host)
            ev['pluginSha256After'] = digest(Path(plugins[role]['path']))
            ev['renders'] = {name: digest(root / role / name) for name in KINDS}
            write_new(root / f'{role}-evidence-finished.json', ev)
            print(f'Completed {role}: four renders; binary/source/input hashes unchanged', flush=True)
        evidence['finishedAt'] = now()
        write_new(root / 'render-evidence.json', evidence)
        role = 'evaluation'
        print('Checking complete artifacts and computing fixed STFT magnitude criterion', flush=True)
        result = evaluate(root)
        write_new(root / 'objective-result.json', result)
        status = {'status': 'evaluated', 'finishedAt': now(),
                  'technicalTargetReached': result['technicalTargetReached'],
                  'worstConditionAndChannelPercent': result['worstConditionAndChannelPercent'],
                  'requiredPercent': 9, 'perceptualEquivalenceEstablished': False,
                  'resultSha256': digest(root / 'objective-result.json')}
        write_new(root / 'status.json', status)
        print(f'Evaluated: worst channel/condition={status["worstConditionAndChannelPercent"]:.6f}%; '
              f'technicalTargetReached={status["technicalTargetReached"]}', flush=True)
        return result
    except Exception as exc:
        # Never touch a preexisting attempt. Partial outputs/logs remain intact.
        if created:
            failure = {'status': 'failed', 'stage': role, 'failedAt': now(),
                       'errorType': type(exc).__name__, 'error': str(exc),
                       'technicalTargetReached': False, 'perceptualEquivalenceEstablished': False,
                       'outputsPreserved': True, 'historicalFallback': False}
            write_new(root / 'status.json', failure)
            print(f'FAILED at {role}: {exc}; partial evidence preserved at {root}', flush=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sourcewav', type=Path)
    parser.add_argument('newroot', type=Path)
    parser.add_argument('--host', required=True, type=Path)
    parser.add_argument('--candidate', type=Path, default=DEFAULT_OPEN)
    parser.add_argument('--reference', type=Path, default=DEFAULT_CEDAR)
    parser.add_argument('--skip-state-snapshot', action='store_true')
    args = parser.parse_args(argv)
    try:
        run(args.sourcewav, args.newroot, args.host, args.candidate, args.reference, args.skip_state_snapshot)
    except Exception as exc:
        print(f'Attempt failed: {type(exc).__name__}: {exc}', flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
