"""Prepare held-out listening material from a NEW supplied WAV; never captures audio.

Record >=60 seconds at 48 kHz, leaving the first second as room/microphone noise,
then speak through seconds 12..59. Frames with energy above the noise baseline
are only a speech-occupancy proxy, not proof of speech or unheard training data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

import numpy as np

from compare_renders import read_wav
from prepare_blind_pilot import KINDS, align_to_input, digest, plugin_info, write_pcm24
from voice_injection import generate, write_wav

KNOWN_TRAINING_SHA = "5efdd3dac24f1cd6d3377654871e8b92c4c0afbc1ca467644e5f77ad419f9fb7"
WORKSPACE = Path(__file__).resolve().parents[4]
PRESERVED_TRAINING = WORKSPACE / "outputs/nean-voice-injection-0.5/inputs/original.wav"
PARAMETERS = {"attenuationDb": -26, "auto": True, "biasDb": 6, "lfBiasDb": 0,
              "mixPercent": 100, "highEndCutDb": 0}


def select_excerpts(signal, rate):
    """Fixed intervals are chosen before listening, independent of plugin output."""
    if (rate != 48000 or signal.ndim != 2 or signal.shape[1] not in (1, 2)
            or not np.isfinite(signal).all() or len(signal) < 58 * rate):
        raise ValueError("Need a new finite mono/stereo WAV of at least 58 seconds at 48 kHz")
    baseline = max(float(np.mean(signal[:rate] ** 2)), 1e-12)
    threshold = baseline * 10 ** (6 / 10)
    frame = rate // 50  # 20ms, all channels, no processing-dependent selection
    rows = []
    for index in range(12):
        start, end = 12 + 4 * index, 15 + 4 * index
        if end * rate > len(signal):
            end = int(len(signal) // rate)
            start = end - 3
        clip = signal[start * rate:end * rate]
        frame_power = np.mean(clip.reshape(-1, frame, signal.shape[1]) ** 2, axis=(1, 2))
        activity = float(np.mean(frame_power > threshold))
        if activity < .35:
            raise ValueError(f"Insufficient speech-like activity at {start}..{end}s ({activity:.0%}); "
                             "supply a new recording with 1s noise-only then speech through 12..59s")
        rows.append({"id": f"evaluation-{index+1:02}", "startSeconds": start, "endSeconds": end,
                     "condition": KINDS[index % len(KINDS)].removesuffix(".wav"),
                     "split": "evaluation", "activeFrameFraction": activity})
    return rows


def validate_source(source, preserved=PRESERVED_TRAINING):
    source_hash = digest(source)
    forbidden = {KNOWN_TRAINING_SHA}
    if preserved.is_file():
        forbidden.add(digest(preserved))
    if source_hash in forbidden:
        raise ValueError("Source matches known tuning material; supply a new held-out recording")
    rate, signal = read_wav(source)
    return source_hash, rate, signal, select_excerpts(signal, rate)


def render_evaluation(host, bundle, inputs, destination, log, duration):
    command = [str(host.resolve()), str(bundle.resolve()), str(inputs.resolve()),
               str(destination.resolve()), "-26", "1", "-65", "0", "realtime", "6"]
    timeout = 4 * (duration + 3) + 60
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(f"Fresh render failed ({result.returncode}); inspect {log}")
    return {"command": command, "timeoutSeconds": timeout}


def prepare(source, output, candidate_bundle, reference_bundle, host):
    source, output = Path(source), Path(output)
    candidate_bundle, reference_bundle, host = Path(candidate_bundle), Path(reference_bundle), Path(host)
    if output.exists():
        raise FileExistsError(f"Refusing overwrite: {output}")
    source_hash, rate, original, selections = validate_source(source)
    if not host.is_file():
        raise FileNotFoundError(host)
    bundles = {"candidate": candidate_bundle, "reference": reference_bundle}
    plugins = {role: plugin_info(bundle) for role, bundle in bundles.items()}
    host_hash = digest(host)
    provenance = {"recordedAt": datetime.now(timezone.utc).isoformat(), "plugins": plugins,
                  "sourceSha256": source_hash, "sourcePath": str(source.resolve()),
                  "sourceDurationSeconds": len(original) / rate, "sampleRate": rate,
                  "parameters": PARAMETERS, "hostSha256": host_hash, "freshRenders": True,
                  "privateRecording": True, "reservedTuningInterval": [0, 10],
                  "guardInterval": [10, 12], "selection": "12 output-independent 3s intervals, 4s stride from12s; final interval moved back if source ends before59s",
                  "checkedKnownTrainingSha256": KNOWN_TRAINING_SHA,
                  "checkedPreservedTrainingPath": str(PRESERVED_TRAINING),
                  "preservedTrainingCopyAvailable": PRESERVED_TRAINING.is_file(),
                  "gainPolicy": "One shared gain across every condition and role; no independent normalization",
                  "limitations": ["One supplied recording and one listener, not independent speakers or sessions.",
                                  "Hash checks detect known exact reuse only; undocumented prior tuning cannot be excluded.",
                                  "Energy activity proxy does not classify speech; initial1s must be noise-only.",
                                  "Human ratings are required; preparation cannot prove perceptual similarity."]}
    output.mkdir(parents=True)
    (output / "provenance-start.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    stimuli = output / "stimuli"
    generate(source, stimuli)
    inputs = stimuli / "inputs"
    # Reuse the same seeded band-limited noise, but include actual transitions
    # within held-out clips rather than only at the generator's original 5s mark.
    _, low_noise = read_wav(inputs / "added_-65.wav")
    t = np.arange(len(original)) / rate
    factor = np.where((t >= 12) & (((t - 12) % 4) >= 1.5), 10.0, 1.0)
    write_wav(inputs / "added_step.wav", original + (low_noise - original) * factor[:, None], rate)
    provenance["stepNoisePolicy"] = "-65/-45dBFS, transitions1.5s into each fixed 4s slot after12s"
    input_hashes = {name: digest(inputs / name) for name in KINDS}
    sources, logs, commands = {}, {}, {}
    try:
        for role, bundle in bundles.items():
            sources[role], logs[role] = output / ("fresh-" + role), output / (role + ".log")
            commands[role] = render_evaluation(host, bundle, inputs, sources[role], logs[role], len(original) / rate)
        if digest(source) != source_hash or digest(host) != host_hash:
            raise ValueError("Source or render host changed during rendering")
        if plugins != {role: plugin_info(bundle) for role, bundle in bundles.items()}:
            raise ValueError("Plugin changed during rendering")
        if input_hashes != {name: digest(inputs / name) for name in KINDS}:
            raise ValueError("Input changed during rendering")
        aligned, audit = {}, []
        for name in KINDS:
            sr, original_input = read_wav(inputs / name)
            aligned[name] = {"anchor": original_input}
            row = {"input": name, "inputSha256": input_hashes[name], "roles": {}}
            for role in bundles:
                log_text = logs[role].read_text(encoding="utf-8")
                match = re.search(r"RENDER " + re.escape(name) + r" latency=(\d+) finite=1", log_text)
                if not match or "PASS renders=4" not in log_text or "text=-26.00" not in log_text or "text=6.00" not in log_text:
                    raise ValueError(f"Missing completion, latency or parameter evidence in {logs[role]}")
                render_path = sources[role] / name
                sr_out, processed = read_wav(render_path)
                if sr != rate or sr_out != rate or len(original_input) != len(original):
                    raise ValueError("Render rate/input length mismatch")
                delay = int(match[1])
                aligned[name][role], measured = align_to_input(original_input, processed, delay)
                row["roles"][role] = {"sha256": digest(render_path), "latencySamples": delay,
                                      "measuredDelays": measured, "logSha256": digest(logs[role])}
            audit.append(row)
        gain = min(1., .95 / max(max(float(np.max(np.abs(x))) for x in roles.values()) for roles in aligned.values()))
        audio_dir = output / "aligned-excerpts"
        audio_dir.mkdir()
        excerpts = []
        for selection in selections:
            row = {k: v for k, v in selection.items() if k != "activeFrameFraction"}
            row["sourceId"] = source_hash
            for role, signal in aligned[row["condition"] + ".wav"].items():
                path = audio_dir / f"{row['id']}-{role}.wav"
                write_pcm24(path, rate, signal[row["startSeconds"] * rate:row["endSeconds"] * rate] * gain)
                row[role] = str(path.resolve())
            excerpts.append(row)
        provenance.update({"commands": commands, "sharedPlaybackGain": gain, "audit": audit,
                           "activityAudit": selections, "status": "awaiting-human-evaluation"})
        spec = {"studyId": "open-dehiss-heldout-v2-" + source_hash[:16], "provenance": provenance, "excerpts": excerpts}
        spec_path = output / "study-spec.json"
        spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        (output / "audit.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        return {"spec": str(spec_path.resolve()), "excerpts": len(excerpts), "status": provenance["status"]}
    except Exception as exc:
        (output / "preparation-failure.json").write_text(json.dumps({"status": "failed", "error": str(exc),
            "historicalFallback": False, "confirmatoryClaim": False}), encoding="utf-8")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--candidate", type=Path, default=Path("C:/Program Files/Common Files/VST3/Open DeHISS.vst3"))
    parser.add_argument("--reference", type=Path, default=Path("C:/Program Files/Common Files/VST3/CEDARAutoDehiss.vst3"))
    parser.add_argument("--host", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.candidate, args.reference, args.host), indent=2))
