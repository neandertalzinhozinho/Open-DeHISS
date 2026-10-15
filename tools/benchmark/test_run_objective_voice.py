"""Runner validation with fake native processes, never real study results."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from compare_renders import read_wav
from prepare_blind_pilot import KINDS, digest
from run_objective_voice import host_environment, main, run
from voice_injection import write_wav


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'attempt'
        self.source = self.base / 'source.wav'
        self.audio = np.random.default_rng(19).normal(0, .02, (300000, 2)).astype(np.float32)
        write_wav(self.source, self.audio, 48000)
        self.host = self.base / 'fake-host.exe'
        self.host.write_bytes(b'unit test fixture, never executed')
        self.bundles = {}
        for role in ('open', 'cedar'):
            bundle = self.base / (role + '.vst3')
            binary = bundle / 'Contents/x86_64-win' / bundle.name
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'unit test fixture plugin ' + role.encode())
            module = bundle / 'Contents/Resources/moduleinfo.json'
            module.parent.mkdir()
            module.write_text(json.dumps({'Name': role, 'Version': 'fixture'}))
            self.bundles[role] = bundle
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def run_fixture(self, **kwargs):
        return run(self.source, self.root, self.host, self.bundles['open'], self.bundles['cedar'], **kwargs)

    def fake_process(self, command, **kwargs):
        role = Path(command[3]).name
        # These immutable records must exist BEFORE the process gets control.
        self.assertTrue((self.root / 'render-evidence-start.json').is_file())
        before = json.loads((self.root / f'{role}-evidence-start.json').read_text())
        self.assertTrue(before['capturedBeforeRender'])
        self.assertEqual(before['host']['sha256'], digest(self.host))
        self.assertEqual(before['command'], command)
        self.assertNotIn('renders', before)
        self.assertNotIn('pluginSha256After', before)
        start = json.loads((self.root / 'render-evidence-start.json').read_text())
        self.assertEqual(start['source']['sha256'], digest(self.source))
        for name in KINDS:
            self.assertEqual(start['inputs'][name], digest(self.root / 'inputs' / name))
        self.assertAlmostEqual(kwargs['timeout'], 4 * (6.25 + 3) + 60)
        self.assertEqual(command[4:], ['-26', '1', '-65', '0', 'offline' if role == 'open' else 'realtime', '6'])
        destination = Path(command[3])
        destination.mkdir()
        params = ({'Attenuation': (.35, '-26.00'), 'Bias': (.8, '6.00'),
                   'Low Frequency Bias': (.5, '0.00'), 'Automatic Threshold': (1, 'on'),
                   'Master Bypass': (0, 'bypass')} if role == 'cedar' else
                  {'Atenuacao (dB)': (.35, '-26.00'), 'Bias (dB)': (.8, '6.00'),
                   'LF Bias (dB)': (.5, '0.00'), 'Automatico': (1, 'On'), 'Bypass': (0, 'Off'),
                   'Mix (%)': (1, '100.00'), 'High End Cut (dB)': (1, '0.00')})
        for name in KINDS:
            rate, audio = read_wav(Path(command[2]) / name)
            write_wav(destination / name, audio * .3, rate)
            for key, (value, text) in params.items():
                kwargs['stdout'].write(f'FINAL {key} normalized={value} text={text}\n')
            kwargs['stdout'].write(f'RENDER {name} latency=0 finite=1 frames={len(audio)}\n')
        kwargs['stdout'].write('PASS renders=4\n')
        return subprocess.CompletedProcess(command, 0)

    def test_complete_flow_captures_before_launch_and_scores(self):
        with patch('run_objective_voice.subprocess.run', side_effect=self.fake_process) as fake:
            result = self.run_fixture(skip_state_snapshot=True)
        self.assertEqual(fake.call_count, 2)
        self.assertEqual(result['worstConditionAndChannelPercent'], 100)
        self.assertFalse(result['perceptualEquivalenceEstablished'])
        evidence = json.loads((self.root / 'render-evidence.json').read_text())
        self.assertEqual(evidence['environmentOverrides'], {'OPEN_DEHISS_HOST_SKIP_STATE_SNAPSHOT': '1'})
        for role in ('open', 'cedar'):
            self.assertEqual(evidence['roles'][role]['pluginSha256After'], evidence['roles'][role]['pluginSha256'])
            self.assertEqual(set(evidence['roles'][role]['renders']), set(KINDS))
        status = json.loads((self.root / 'status.json').read_text())
        self.assertEqual(status['status'], 'evaluated')
        self.assertEqual(status['resultSha256'], digest(self.root / 'objective-result.json'))

    def test_failure_preserves_partial_outputs_and_never_scores(self):
        def fail(command, **kwargs):
            destination = Path(command[3]);destination.mkdir()
            (destination / 'partial.wav').write_bytes(b'partial fixture')
            kwargs['stdout'].write('fixture native crash\n')
            return subprocess.CompletedProcess(command, -123)
        with patch('run_objective_voice.subprocess.run', side_effect=fail) as fake:
            with self.assertRaisesRegex(RuntimeError, 'exit -123'): self.run_fixture()
        self.assertEqual(fake.call_count, 1)
        self.assertTrue((self.root / 'open/partial.wav').exists())
        self.assertFalse((self.root / 'objective-result.json').exists())
        self.assertFalse((self.root / 'render-evidence.json').exists())
        status = json.loads((self.root / 'status.json').read_text())
        self.assertEqual(status['status'], 'failed')
        self.assertFalse(status['historicalFallback'])

    def test_timeout_preserves_failure_log(self):
        def timeout(command, **kwargs):
            kwargs['stdout'].write('fixture waiting at load\n')
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        with patch('run_objective_voice.subprocess.run', side_effect=timeout):
            with self.assertRaises(subprocess.TimeoutExpired): self.run_fixture()
        self.assertIn('waiting at load', (self.root / 'open-host.log').read_text())
        self.assertFalse((self.root / 'objective-result.json').exists())
        self.assertEqual(json.loads((self.root / 'status.json').read_text())['errorType'], 'TimeoutExpired')

    def test_changed_host_plugin_source_and_input_rejected(self):
        for target in ('host', 'plugin', 'source', 'input'):
            with self.subTest(target=target):
                attempt = self.base / ('attempt-' + target)
                original_root = self.root;self.root = attempt
                path = {'host': self.host, 'plugin': self.bundles['open'] / 'Contents/x86_64-win/open.vst3',
                        'source': self.source, 'input': attempt / 'inputs/original.wav'}[target]
                saved = path.read_bytes() if path.exists() else None
                def change(command, **kwargs):
                    process = self.fake_process(command, **kwargs)
                    path.write_bytes(path.read_bytes() + b'changed')
                    return process
                try:
                    with patch('run_objective_voice.subprocess.run', side_effect=change):
                        with self.assertRaisesRegex(ValueError, 'changed'): self.run_fixture()
                    self.assertFalse((attempt / 'objective-result.json').exists())
                    self.assertEqual(json.loads((attempt / 'status.json').read_text())['status'], 'failed')
                finally:
                    if saved is not None: path.write_bytes(saved)
                    self.root = original_root

    def test_existing_attempt_never_modified_or_launched(self):
        self.root.mkdir();marker = self.root / 'important.json';marker.write_text('preserve')
        with patch('run_objective_voice.subprocess.run') as fake:
            with self.assertRaises(FileExistsError): self.run_fixture()
        fake.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [marker])
        self.assertEqual(marker.read_text(), 'preserve')

    def test_environment_case_dedup_without_secrets_in_provenance(self):
        with patch.dict(os.environ, {'Path': 'one', 'PATH': 'two', 'FiXtUrE_SeCrEt': 'never record'}, clear=True):
            env = host_environment(False)
        self.assertEqual(set(env), {'PATH', 'FIXTURE_SECRET', 'OPEN_DEHISS_HOST_SKIP_STATE_SNAPSHOT'})
        self.assertEqual(env['OPEN_DEHISS_HOST_SKIP_STATE_SNAPSHOT'], '0')
        with patch('run_objective_voice.subprocess.run', side_effect=self.fake_process): self.run_fixture()
        self.assertEqual(json.loads((self.root / 'render-evidence.json').read_text())['environmentOverrides'],
                         {'OPEN_DEHISS_HOST_SKIP_STATE_SNAPSHOT': '0'})

    def test_cli_flag_and_paths(self):
        args = [str(self.source), str(self.root), '--host', str(self.host),
                '--candidate', str(self.bundles['open']), '--reference', str(self.bundles['cedar']),
                '--skip-state-snapshot']
        with patch('run_objective_voice.run') as fake:
            self.assertEqual(main(args), 0)
        self.assertEqual(fake.call_args.args[-1], True)
        with patch('run_objective_voice.run', side_effect=RuntimeError('fixture failed')):
            self.assertEqual(main(args), 1)

    def test_mono_source_rejected_before_generation(self):
        write_wav(self.source, self.audio[:, :1], 48000)
        with patch('run_objective_voice.subprocess.run') as fake:
            with self.assertRaisesRegex(ValueError, 'stereo'): self.run_fixture()
        fake.assert_not_called()
        self.assertFalse(self.root.exists())


if __name__ == '__main__':
    unittest.main()
