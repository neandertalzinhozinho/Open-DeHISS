"""Package an offline, blinded two-session listening study. Never manufactures scores."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil

import numpy as np
from scipy.io import wavfile

ROLES = ("reference", "candidate", "anchor")
FORMAT = "open-dehiss-blind-manifest-v2"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _public_provenance(provenance):
    """Allow only simple plugin identity fields; paths/parameters remain in private key."""
    source = provenance.get("plugins", [])
    if isinstance(source, dict):
        source = list(source.values())
    if not isinstance(source, list):
        return {}
    plugins = []
    for item in source:
        if not isinstance(item, dict):
            continue
        clean = {}
        for name in ("name", "version", "sha256"):
            val = item.get(name)
            if isinstance(val, str) and not any(x in val for x in ("/", "\\", ":")):
                clean[name] = val
        if clean:
            plugins.append(clean)
    return {"plugins": plugins} if plugins else {}


def build(spec_path, output, seed=20261013):
    spec_path, output = Path(spec_path), Path(output)
    if type(seed) is not int or seed != 20261013:
        raise ValueError("The fixed v2 protocol requires seed=20261013")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite study: {output}")
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    study_id = spec.get("studyId")
    excerpts = spec.get("excerpts")
    provenance = spec.get("provenance", {})
    if not isinstance(study_id, str) or not study_id.strip():
        raise ValueError("studyId must be a nonempty string")
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")
    if not isinstance(excerpts, list) or not excerpts:
        raise ValueError("At least one excerpt is required")
    seen, validated, intervals = set(), [], {}
    for excerpt in excerpts:
        ident = excerpt.get("id")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("Excerpt IDs must be nonempty and unique")
        seen.add(ident)
        if excerpt.get("split") not in ("evaluation", "pilot"):
            raise ValueError("Each excerpt must specify evaluation or pilot split")
        if not isinstance(excerpt.get("sourceId"), str) or not excerpt["sourceId"]:
            raise ValueError("sourceId is required")
        if not isinstance(excerpt.get("condition"), str):
            raise ValueError("condition must be a string")
        start, end = excerpt.get("startSeconds"), excerpt.get("endSeconds")
        if not _number(start) or not _number(end) or start < 0 or end <= start:
            raise ValueError("Excerpt interval must be finite, nonnegative and nonempty")
        if excerpt["split"] == "evaluation" and end - start < 3:
            raise ValueError("Evaluation excerpts must be at least 3 seconds long")
        signatures, files = [], {}
        for role in ROLES:
            path = Path(excerpt.get(role, ""))
            if not path.is_absolute() or not path.is_file() or path.suffix.lower() != ".wav":
                raise ValueError(f"{ident}/{role}: absolute existing WAV path required")
            rate, samples = wavfile.read(path)
            if rate <= 0 or samples.size == 0 or samples.ndim not in (1, 2):
                raise ValueError(f"{ident}/{role}: invalid audio")
            channels = 1 if samples.ndim == 1 else samples.shape[1]
            if channels not in (1, 2) or not np.isfinite(samples).all():
                raise ValueError(f"{ident}/{role}: invalid channels or non-finite audio")
            signatures.append((rate, len(samples), channels))
            files[role] = path
        if len(set(signatures)) != 1:
            raise ValueError(f"{ident}: WAV rates, lengths and channels must match after alignment")
        rate, length, _ = signatures[0]
        if abs(length / rate - (end - start)) > 2 / rate:
            raise ValueError(f"{ident}: source interval and WAV duration disagree")
        source_intervals = intervals.setdefault(excerpt["sourceId"], [])
        if any(start < old_end and end > old_start and (excerpt["split"] == "evaluation" or old_split == "evaluation")
               for old_start, old_end, old_split in source_intervals):
            raise ValueError("Evaluation excerpts must not overlap pilot or other evaluation excerpts")
        source_intervals.append((start, end, excerpt["split"]))
        validated.append((excerpt, files, length / rate))
    evaluation_count = sum(e[0]["split"] == "evaluation" for e in validated)
    protocol = {"requiredPercent": 9, "confidenceLevel": 0.95, "nResamples": 9999,
                "seed": seed, "minDistinctExcerpts": 12, "sessionIds": ["s1", "s2"]}
    public_protocol = {k: v for k, v in protocol.items() if k != "seed"}
    public_protocol.update({"evaluationExcerptCount": evaluation_count,
                            "confirmatoryEligible": evaluation_count >= 12,
                            "status": "awaiting-human-ratings" if evaluation_count >= 12 else "pilot-insufficient-excerpts"})
    rng = random.Random(seed)
    trials, secret_trials, copies = [], [], []
    for session in protocol["sessionIds"]:
        order = [(e, files, role) for e, files, _ in validated for role in ROLES]
        rng.shuffle(order)
        for excerpt, files, role in order:
            ident = f"t{rng.getrandbits(128):032x}"
            a, b = f"audio/{ident}-a.wav", f"audio/{ident}-b.wav"
            trials.append({"id": ident, "sessionId": session, "excerptId": excerpt["id"],
                           "a": a, "b": b, "sha256A": sha256(files["reference"]),
                           "sha256B": sha256(files[role])})
            secret_trials.append({"id": ident, "sessionId": session, "excerptId": excerpt["id"], "role": role})
            copies.extend(((files["reference"], a), (files[role], b)))
    manifest = {"format": FORMAT, "studyId": study_id, "protocol": public_protocol,
                "excerpts": [{"id": e["id"], "durationSeconds": duration, "split": e["split"]}
                             for e, _, duration in validated],
                "trials": trials, "provenance": _public_provenance(provenance)}
    encoded = _json_bytes(manifest)
    digest = hashlib.sha256(encoded).hexdigest()
    key = {"format": "open-dehiss-blind-key-v2", "studyId": study_id, "manifestSha256": digest,
           "protocol": protocol, "provenance": provenance,
           "excerpts": [{k: e[k] for k in ("id", "sourceId", "startSeconds", "endSeconds", "condition", "split")}
                        for e, _, _ in validated], "trials": secret_trials}
    # Validate everything, including template availability and JSON serializability, before mkdir.
    private_encoded = _json_bytes(key)
    template = Path(__file__).with_name("blind_study.html").read_text(encoding="utf-8")
    embedded = json.dumps({"manifest": manifest, "manifestSha256": digest}, ensure_ascii=False).replace("<", "\\u003c")
    html = template.replace("/*__STUDY_DATA__*/ null", embedded)
    output.mkdir(parents=True, exist_ok=False)
    (output / "audio").mkdir()
    (output / "private").mkdir()
    for src, relative in copies:
        shutil.copyfile(src, output / relative)
    (output / "manifest.json").write_bytes(encoded)
    (output / "private" / "key.json").write_bytes(private_encoded)
    (output / "index.html").write_text(html, encoding="utf-8")
    return {"manifest": manifest, "key": key, "output": str(output), "manifestSha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261013)
    args = parser.parse_args()
    result = build(args.spec, args.output, args.seed)
    print(json.dumps({"output": result["output"], "manifestSha256": result["manifestSha256"],
                      "trials": len(result["manifest"]["trials"]), "protocol": result["manifest"]["protocol"]}, indent=2))


if __name__ == "__main__":
    main()
