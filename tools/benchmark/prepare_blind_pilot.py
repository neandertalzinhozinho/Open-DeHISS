"""Audit and align the existing private voice corpus for a descriptive pilot.

An optional fresh render uses the normal VST3 host and installed plugins. Nothing
is recorded from a device. Historical renders are never silently substituted for
a failed fresh render. The four noise variants share ONE recording, already used
for tuning, so this corpus cannot support the confirmatory perceptual claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from audio_metrics import estimate_delay, rms_db
from compare_renders import read_wav

KINDS = ("original.wav", "added_-65.wav", "added_-55.wav", "added_step.wav")
EXPECTED_BETA09 = "fa156512ac6798b878afbc5c2b61c15d1a9a2a03faf281ebb2a881d4269578cb"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_pcm24(path, sample_rate, signal):
    """Browser-compatible PCM with quantization well below the measured hiss."""
    if signal.ndim != 2 or not np.isfinite(signal).all() or np.max(np.abs(signal)) > 1:
        raise ValueError("Need finite, non-clipping frames x channels audio")
    integers = np.rint(signal * 8388607).astype("<i4")
    payload = integers.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(signal.shape[1])
        stream.setsampwidth(3)
        stream.setframerate(sample_rate)
        stream.writeframes(payload)


def plugin_info(bundle):
    binary = bundle / "Contents/x86_64-win" / bundle.name
    module = bundle / "Contents/Resources/moduleinfo.json"
    # The VST SDK writes trailing commas, so read these two fields without
    # pretending the file is strict JSON or modifying the installed metadata.
    text = module.read_text(encoding="utf-8")
    return {"name": re.search(r'"Name"\s*:\s*"([^"]+)"', text)[1],
            "version": re.search(r'"Version"\s*:\s*"([^"]+)"', text)[1],
            "sha256": digest(binary), "path": str(binary.resolve()),
            "moduleInfoSha256": digest(module)}


def align_to_input(original, processed, expected_delay):
    if original.ndim != 2 or processed.ndim != 2 or original.shape[1] != processed.shape[1]:
        raise ValueError("Channel mismatch")
    if not np.isfinite(original).all() or not np.isfinite(processed).all():
        raise ValueError("Nonfinite samples")
    delays = [estimate_delay(original[:, ch], processed[:, ch], 32768)
              for ch in range(original.shape[1])]
    if any(abs(delay - expected_delay) > 1 for delay in delays):
        raise ValueError(f"Delay inconsistent with render log: {delays} vs {expected_delay}")
    if len(processed) < expected_delay + len(original):
        raise ValueError("Missing processed tail")
    aligned = processed[expected_delay:expected_delay + len(original)]
    return aligned, delays


def render(host, bundle, inputs, destination, log, timeout=90):
    command = [str(host.resolve()), str(bundle.resolve()), str(inputs.resolve()),
               str(destination.resolve()), "-26", "1", "-65", "0", "realtime", "6"]
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(f"Render failed ({result.returncode}); see {log}")
    return command


def prepare(corpus, output, candidate_bundle, reference_bundle, host=None):
    if output.exists():
        raise FileExistsError(f"Refusing overwrite: {output}")
    plugins = {"candidate": plugin_info(candidate_bundle), "reference": plugin_info(reference_bundle)}
    if plugins["candidate"]["sha256"] != EXPECTED_BETA09:
        raise ValueError("Installed candidate is not the recorded beta 0.9 binary")
    inputs = corpus / "inputs"
    sources = {"candidate": corpus / "nine-vst3-bias6", "reference": corpus / "cedar-bias6"}
    logs = {"candidate": corpus / "nine-vst3-bias6-host.txt", "reference": corpus / "cedar-bias6-host.txt"}
    for name in KINDS:
        if not (inputs / name).is_file():
            raise FileNotFoundError(inputs / name)
    output.mkdir(parents=True)
    provenance = {"recordedAt": datetime.now(timezone.utc).isoformat(), "plugins": plugins,
                  "parameters": {"attenuationDb": -26, "auto": True, "biasDb": 6,
                                 "lfBiasDb": 0, "mixPercent": 100, "highEndCutDb": 0},
                  "privateRecording": True, "freshRenders": bool(host),
                  "sourceManifest": json.loads((corpus / "manifest.json").read_text(encoding="utf-8")),
                  "originalSourceFileAvailable": False,
                  "inputCopySha256": digest(inputs / "original.wav"),
                  "gainPolicy": "No independent normalization; one shared playback gain for all conditions/roles",
                  "limitations": ["The original source path is unavailable; the preserved float WAV copy is used.",
                                  "All four variants derive from one 10.26-second recording already used for tuning.",
                                  "Pilot only: no held-out set and fewer than 12 distinct excerpts."]}
    (output / "provenance-start.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    if host:
        provenance["hostSha256"] = digest(host)
        provenance["commands"] = {}
        for role, bundle in (("candidate", candidate_bundle), ("reference", reference_bundle)):
            sources[role] = output / f"fresh-{role}"
            logs[role] = output / f"fresh-{role}.log"
            try:
                provenance["commands"][role] = render(host, bundle, inputs, sources[role], logs[role])
            except (subprocess.TimeoutExpired, RuntimeError) as exc:
                (output / "render-failure.json").write_text(json.dumps({"role": role, "error": str(exc),
                    "status": "blocked", "historicalFallback": False}, indent=2), encoding="utf-8")
                raise
        if plugins != {"candidate": plugin_info(candidate_bundle), "reference": plugin_info(reference_bundle)}:
            raise ValueError("Plugin changed during render")
    else:
        provenance["limitations"].append("Installed hashes measured now do not prove historical render binary identity.")
    aligned = {}
    audit = []
    rate0 = None
    for name in KINDS:
        rate, x = read_wav(inputs / name)
        if rate0 is None:
            rate0 = rate
        if rate != rate0 or len(x) / rate < 9.5:
            raise ValueError("Input rates or durations do not match pilot interval")
        row = {"input": name, "inputSha256": digest(inputs / name), "sampleRate": rate,
               "inputFrames": len(x), "inputRmsDbfs": rms_db(x), "roles": {}}
        aligned[name] = {"anchor": x}
        for role in ("reference", "candidate"):
            path = sources[role] / name
            sr, y = read_wav(path)
            if sr != rate:
                raise ValueError("Sample rate mismatch")
            log_text = logs[role].read_text(encoding="utf-8")
            match = re.search(r"RENDER " + re.escape(name) + r" latency=(\d+) finite=1", log_text)
            if not match or "PASS renders=4" not in log_text:
                raise ValueError(f"Incomplete render log: {logs[role]}")
            if "text=-26.00" not in log_text or "text=6.00" not in log_text:
                raise ValueError("Missing parameter evidence")
            delay = int(match[1])
            y, measured = align_to_input(x, y, delay)
            aligned[name][role] = y
            row["roles"][role] = {"path": str(path.resolve()), "sha256": digest(path),
                                  "logSha256": digest(logs[role]), "latencySamples": delay,
                                  "measuredDelays": measured, "alignedRmsDbfs": rms_db(y),
                                  "differenceFromInputRmsDbfs": rms_db(y - x)}
        audit.append(row)
    # Common gain avoids clipping while retaining every relative gain difference.
    peak = max(float(np.max(np.abs(signal))) for roles in aligned.values() for signal in roles.values())
    shared_gain = min(1.0, 0.95 / max(peak, 1e-30))
    provenance.update({"sharedPlaybackGain": shared_gain, "audit": audit,
                       "listeningWavFormat": "PCM24, identical conversion, original float renders retained",
                       "distinctSourceRecordings": 1, "sourceDurationSeconds": audit[0]["inputFrames"] / rate0,
                       "status": "pilot_only_need_fresh_voice"})
    excerpts = []
    audio_dir = output / "aligned-excerpts"
    audio_dir.mkdir()
    for index, name in enumerate(KINDS, 1):
        excerpt = {"id": f"pilot-{index}", "sourceId": provenance["sourceManifest"]["sourceSha256"],
                   "startSeconds": 1.5, "endSeconds": 9.5, "condition": name.removesuffix(".wav"),
                   "split": "pilot"}
        for role, signal in aligned[name].items():
            clip = signal[int(1.5 * rate0):int(9.5 * rate0)] * shared_gain
            path = audio_dir / f"{index}-{role}.wav"
            # Same high-resolution conversion for all roles; original float
            # renders retained intact. No independent level normalization.
            write_pcm24(path, rate0, clip)
            excerpt[role] = str(path.resolve())
        excerpts.append(excerpt)
    spec = {"studyId": "open-dehiss-beta09-personal-pilot-v2", "provenance": provenance, "excerpts": excerpts}
    (output / "study-spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    (output / "audit.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return {"spec": str((output / "study-spec.json").resolve()), "status": provenance["status"],
            "excerpts": len(excerpts), "independentNewEvaluationExcerpts": 0, "freshRenders": bool(host)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--candidate", type=Path, default=Path("C:/Program Files/Common Files/VST3/Open DeHISS.vst3"))
    parser.add_argument("--reference", type=Path, default=Path("C:/Program Files/Common Files/VST3/CEDARAutoDehiss.vst3"))
    parser.add_argument("--host", type=Path, help="Optional installed-plugin fresh renders, realtime, max 90s each")
    args = parser.parse_args()
    print(json.dumps(prepare(args.corpus, args.output, args.candidate, args.reference, args.host), indent=2))
