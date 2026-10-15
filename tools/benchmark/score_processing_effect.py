"""Diagnose agreement of processing effects, not perceptual equivalence.

The dry control has normalized effect error exactly 1 wherever the reference
changes the input materially. There is deliberately no percentage or pass mark.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import scipy
from scipy.signal import stft

from compare_renders import read_wav
from prepare_blind_pilot import KINDS, align_to_input, digest
from score_objective_voice import evaluate as validate_objective_evidence, _render_records


BANDS = ((80, 800), (800, 2000), (2000, 6000), (800, 6000),
         (6000, 15000), (15000, 24000))
INPUT_FLOOR_DBFS = -80.0
MATERIAL_EFFECT_RELATIVE_DB = -20.0
NFFT = 2048
HOP = 1024
DB_FLOOR_POWER = 1e-30


def _db(power):
    return float(10 * np.log10(max(float(power), DB_FLOOR_POWER)))


def _validate_audio(original, reference, candidate, rate):
    arrays = [np.asarray(a, dtype=np.float64) for a in (original, reference, candidate)]
    if (not isinstance(rate, (int, np.integer)) or isinstance(rate, bool)
            or rate < 12000):
        raise ValueError("Need integer sample rate >= 12000 Hz")
    if (arrays[0].ndim != 2 or arrays[0].shape[0] < NFFT
            or arrays[0].shape[1] < 1 or any(a.shape != arrays[0].shape for a in arrays)
            or any(not np.isfinite(a).all() for a in arrays)):
        raise ValueError("Need equal finite frames x channels arrays, at least 2048 frames")
    return arrays


def align_render(original, processed, expected_delay):
    """Reject impossible metadata before the existing independent delay check."""
    if (not isinstance(expected_delay, (int, np.integer)) or isinstance(expected_delay, bool)
            or not 0 <= expected_delay <= 32768):
        raise ValueError("Expected delay must be an integer in [0, 32768]")
    if len(original) < NFFT:
        raise ValueError("Insufficient input for delay audit")
    aligned, measured = align_to_input(original, processed, expected_delay)
    if any(delay != expected_delay for delay in measured):
        raise ValueError(f'Exact integer alignment required: measured {measured}, declared {expected_delay}')
    return aligned, measured


def _powers(x, r, c, weights):
    """One-sided PSD integration; retain complex phase in the removed signal."""
    def energy(a):
        try:
            with np.errstate(over="raise", invalid="raise"):
                value = float(np.mean(np.sum(np.abs(a) ** 2 * weights[:, None], axis=0)))
        except FloatingPointError as exc:
            raise ValueError("Nonfinite analysis power") from exc
        if not np.isfinite(value):
            raise ValueError("Nonfinite analysis power")
        return value

    er, ec = x - r, x - c
    input_power, reference_power, candidate_power = energy(x), energy(r), energy(c)
    ref_effect, candidate_effect = energy(er), energy(ec)
    error = energy(ec - er)
    input_db = _db(input_power)
    ref_relative = _db(ref_effect / max(input_power, DB_FLOOR_POWER))
    candidate_relative = _db(candidate_effect / max(input_power, DB_FLOOR_POWER))
    material = input_db > INPUT_FLOOR_DBFS and ref_relative >= MATERIAL_EFFECT_RELATIVE_DB
    projection = float(np.mean(np.sum(np.real(np.conj(er) * ec)
                                     * weights[:, None], axis=0)))
    return {
        "inputPower": input_power, "referenceEffectPower": ref_effect,
        "candidateEffectPower": candidate_effect, "effectErrorPower": error,
        "inputRmsDbfs": input_db, "referenceOutputRmsDbfs": _db(reference_power),
        "candidateOutputRmsDbfs": _db(candidate_power),
        "referenceRmsReductionDb": input_db - _db(reference_power),
        "candidateRmsReductionDb": input_db - _db(candidate_power),
        "candidateMinusReferenceOutputDb": _db(candidate_power) - _db(reference_power),
        "referenceEffectRelativeToInputDb": ref_relative,
        "candidateEffectRelativeToInputDb": candidate_relative,
        "referenceMaterialEffect": material,
        "candidateMaterialEffect": input_db > INPUT_FLOOR_DBFS
            and candidate_relative >= MATERIAL_EFFECT_RELATIVE_DB,
        "referenceAtLeast1DbAttenuation": input_db > INPUT_FLOOR_DBFS
            and input_db - _db(reference_power) >= 1.0,
        "normalizedEffectError": error / ref_effect if material else None,
        "effectErrorRelativeToReferenceDb": _db(error / ref_effect) if material else None,
        "effectProjectionOnReference": projection / ref_effect if material else None,
        "effectCosine": float(np.clip(projection / np.sqrt(ref_effect * candidate_effect), -1, 1))
            if material and candidate_effect > 0 else None,
        "exactEffectMatch": error == 0,
    }


def _aggregate(rows):
    active = [r for r in rows if r["referenceMaterialEffect"]]
    error = sum(r["effectErrorPower"] * r["durationSeconds"] for r in active)
    effect = sum(r["referenceEffectPower"] * r["durationSeconds"] for r in active)
    errors = [r["normalizedEffectError"] for r in active]
    level_deltas = [r["candidateMinusReferenceOutputDb"] for r in active]
    return {
        "windows": len(rows), "materialReferenceWindows": len(active),
        "referenceAttenuatingAtLeast1DbWindows": sum(r["referenceAtLeast1DbAttenuation"] for r in rows),
        "materialCandidateWindows": sum(r["candidateMaterialEffect"] for r in rows),
        "materialReferenceButCandidateBelowThresholdWindows": sum(not r["candidateMaterialEffect"] for r in active),
        "materialReferenceDurationSeconds": sum(r["durationSeconds"] for r in active),
        "normalizedEffectError": error / effect if effect > 0 else None,
        "medianWindowNormalizedEffectError": float(np.median(errors)) if errors else None,
        "p95WindowNormalizedEffectError": float(np.quantile(errors, .95)) if errors else None,
        "medianCandidateMinusReferenceOutputDb": float(np.median(level_deltas)) if level_deltas else None,
        "p95AbsoluteCandidateMinusReferenceOutputDb": float(np.quantile(np.abs(level_deltas), .95)) if level_deltas else None,
        "dryControlNormalizedEffectError": 1.0 if effect > 0 else None,
        "identicalReferenceControlNormalizedEffectError": 0.0 if effect > 0 else None,
        "status": "diagnostic_available" if active else "inconclusive_no_material_reference_effect",
    }


def compare_aligned(original, reference, candidate, rate, start_seconds=1.5):
    """Analyze already aligned arrays without any gain fitting or resampling."""
    x, r, c = _validate_audio(original, reference, candidate, rate)
    if (not isinstance(start_seconds, (int, float)) or isinstance(start_seconds, bool)
            or not np.isfinite(start_seconds) or start_seconds < 0):
        raise ValueError("Invalid analysis start")
    start = int(round(start_seconds * rate))
    if len(x) - start < NFFT:
        raise ValueError("Insufficient frames after analysis start")
    windows = []
    for begin in range(start, len(x), rate):
        end = min(begin + rate, len(x))
        if end - begin < NFFT:
            break
        for channel in range(x.shape[1]):
            spectra = []
            for audio in (x, r, c):
                f, _, z = stft(audio[begin:end, channel], fs=rate, window="hann",
                               nperseg=NFFT, noverlap=NFFT - HOP, boundary="zeros",
                               padded=True, detrend=False, scaling="psd")
                if not np.isfinite(z).all():
                    raise ValueError("Nonfinite analysis spectrum")
                spectra.append(z)
            weights = np.full(len(f), 2.0 * rate / NFFT)
            weights[0] *= .5
            weights[-1] *= .5
            for low, high in BANDS:
                # Upper-exclusive bands never count shared edges twice. The
                # diagnostic 800-6000 aggregate overlaps its two subdivisions.
                selected = (f >= low) & (f < min(high, rate / 2))
                if not selected.any():
                    continue
                stats = _powers(*(a[selected] for a in spectra), weights[selected])
                windows.append({"channel": channel, "bandHz": [low, min(high, rate / 2)],
                                "startSeconds": begin / rate, "endSeconds": end / rate,
                                "durationSeconds": (end - begin) / rate, **stats})
    summaries = []
    keys = sorted({(r["channel"], *r["bandHz"]) for r in windows})
    for channel, low, high in keys:
        group = [r for r in windows if r["channel"] == channel and r["bandHz"] == [low, high]]
        summaries.append({"channel": channel, "bandHz": [low, high], **_aggregate(group)})
    return {"analysisRevision": 2,
            "boundaryPolicy": "Each retained window is zero-extended at both boundaries and padded to full STFT coverage; boundary power is affected by this common windowing",
            "summaries": summaries, "windows": windows}


def evaluate(root):
    """Reuse the full fixed-protocol provenance audit before deriving a report."""
    root = Path(root).resolve()
    audited = validate_objective_evidence(root)
    records = {role: _render_records((root / (role + "-host.log")).read_text(encoding="utf-8"), role)
               for role in ("cedar", "open")}
    conditions = []
    for name in KINDS:
        hashes = next(row for row in audited["conditions"] if row["condition"] == name)
        rate, x = read_wav(root / "inputs" / name)
        if digest(root / "inputs" / name) != hashes["inputSha256"]:
            raise ValueError("Input changed after provenance audit")
        aligned, measured = {}, {}
        for role in ("cedar", "open"):
            sr, y = read_wav(root / role / name)
            expected = hashes["referenceSha256" if role == "cedar" else "candidateSha256"]
            if digest(root / role / name) != expected:
                raise ValueError("Render changed after provenance audit")
            if sr != rate:
                raise ValueError("Render sample rate differs from input")
            aligned[role], measured[role] = align_render(x, y, records[role][name]["latency"])
        conditions.append({"condition": name, "inputSha256": hashes["inputSha256"],
                           "referenceSha256": hashes["referenceSha256"],
                           "candidateSha256": hashes["candidateSha256"], "measuredDelays": measured,
                           **compare_aligned(x, aligned["cedar"], aligned["open"], rate)})
    return {
        "schema": "processing-effect-diagnostic-v2",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceRoot": str(root), "renderEvidenceSha256": digest(root / "render-evidence.json"),
        "sourceSha256": audited["protocol"]["sourceSha256"],
        "pluginProtocol": audited["protocol"],
        "analysisCodeSha256": digest(Path(__file__)),
        "numpyVersion": np.__version__, "scipyVersion": scipy.__version__,
        "provenanceAudit": "score_objective_voice.evaluate completed without error",
        "originalFixedTechnicalResult": {
            "worstConditionAndChannelPercent": audited["worstConditionAndChannelPercent"],
            "requiredPercent": audited["requiredPercent"],
            "technicalTargetReached": audited["technicalTargetReached"],
        },
        "analysis": {"startSeconds": 1.5, "windowSeconds": 1.0, "stftWindow": "hann",
                     "nperseg": NFFT, "noverlap": NFFT - HOP, "boundary": "zeros", "padded": True,
                     "inputFloorDbfsExclusive": INPUT_FLOOR_DBFS,
                     "materialReferenceEffectRelativeToInputDbInclusive": MATERIAL_EFFECT_RELATIVE_DB,
                     "independentGainNormalization": False, "powerDbFloor": -300,
                     "formula": "sum(|(X-C)-(X-R)|^2) / sum(|X-R|^2), complex spectra",
                     "interpretation": "0 identical effect; 1 dry control; >1 error exceeds dry control",
                     "aggregation": "effect-energy-weighted over eligible windows, within each band/channel"},
        "conditions": conditions,
        "perceptualEquivalenceEstablished": False,
        "limitations": [
            "Diagnostic only, no new equivalence percentage or pass mark.",
            "Removed signal includes speech, phase differences and artifacts, not identified noise alone.",
            "No clean voice ground truth: matching the reference effect does not prove quality or intelligibility.",
            "Material-effect thresholds select reference processing activity, not speech/noise labels.",
            "The 800-6000 Hz aggregate overlaps two bands; never pool all band rows into one total.",
            "Energy weighting can emphasize loud windows; per-window median/p95 and full rows are retained.",
            "Four noise conditions share one recording; windows and channels are not independent trials.",
            "Alignment uses measured integer latency only; fractional delay or phase response remains in the error.",
            "Each retained window is zero-extended; common boundary weighting affects absolute power estimates.",
            "First 1.5 seconds excluded by the previous protocol; no claim these seconds contain silence.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path, help="New JSON file; existing files are never overwritten")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite existing report")
    report = evaluate(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps({"output": str(args.output.resolve()), "conditions": [
        {"condition": item["condition"], "band800to6000": [r for r in item["summaries"] if r["bandHz"] == [800, 6000]]}
        for item in report["conditions"]]}, indent=2, allow_nan=False))
