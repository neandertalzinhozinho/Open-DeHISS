"""Score explicit listening ratings; objective metrics cannot supply ratings.

V2 inference is conditional on this listener and material, using paired excerpt
clusters retaining both sessions and all roles. Legacy data is descriptive only.
"""
import argparse
from collections import defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import re
import statistics
import warnings

ROLES = ("candidate", "reference", "anchor")
PROTOCOL = {
    "requiredPercent": 9, "confidenceLevel": 0.95, "nResamples": 9999,
    "seed": 20261013, "minDistinctExcerpts": 12, "sessionIds": ["s1", "s2"],
}
LIMITATIONS = (
    "Conditional similarity index for this listener, excerpts, parameters and "
    "plugin versions, not percentage algorithm equivalence or a population estimate. "
    "Excerpt bootstrap assumes exchangeability of excerpts; excerpts from the same "
    "recording are not independent speakers or recording sessions. Playback flags "
    "record interface events and do not prove listening or attention."
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path):
    result = json.loads(Path(path).read_text(encoding="utf-8-sig"),
                        object_pairs_hook=_unique_object)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, label, minimum=None, maximum=None):
    _require(type(value) in (int, float) and math.isfinite(value),
             f"{label} must be a finite numeric value")
    _require(minimum is None or value >= minimum, f"{label} below {minimum}")
    _require(maximum is None or value <= maximum, f"{label} above {maximum}")
    return float(value)


def _text(value, label):
    _require(isinstance(value, str) and bool(value.strip()), f"Missing {label}")
    return value


def _time(value, label):
    _text(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid ISO timestamp: {label}") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
             f"Timestamp requires timezone: {label}")
    return parsed


def _normalized(medians):
    span = medians["reference"] - medians["anchor"]
    return None if span <= 0 else 100 * (medians["candidate"] - medians["anchor"]) / span


def _display(value):
    return None if value is None else max(0.0, min(100.0, value))


def _legacy(key, ratings):
    _require(isinstance(ratings.get("scores"), dict), "Missing scores object")
    _require(set(ratings["scores"]) == set(key), "Missing or extra trial scores")
    groups = {role: [] for role in ROLES}
    for trial, role in key.items():
        _require(role in ROLES, f"Unknown legacy role: {role}")
        groups[role].append(_number(ratings["scores"][trial], trial, 0, 100))
    _require(all(groups.values()), "All three roles are required")
    medians = {role: statistics.median(values) for role, values in groups.items()}
    raw = _normalized(medians)
    return {
        "format": "open-dehiss-blind-report-legacy-descriptive",
        "method": "reference-anchored blind similarity; legacy descriptive only",
        "medians": medians, "rawNormalizedSimilarityPercent": raw,
        "normalizedSimilarityPercent": _display(raw), "requiredPercent": 9,
        "validScale": medians["reference"] >= 90 and medians["reference"] - medians["anchor"] >= 20,
        "targetReached": False, "status": "inconclusive", "decision": "inconclusive",
        "reasons": ["Legacy data has no verified sessions, explicit playback, provenance or excerpt clusters."],
        "limitations": LIMITATIONS,
    }


def _validate(key, ratings):
    _require(key.get("format") == "open-dehiss-blind-key-v2", "Unsupported key format")
    _require(ratings.get("format") == "open-dehiss-blind-scores-v2", "Unsupported scores format")
    for name in ("studyId", "manifestSha256"):
        _text(key.get(name), name)
        _require(ratings.get(name) == key[name], f"Mismatched {name}")
    _require(re.fullmatch(r"[0-9a-fA-F]{64}", key["manifestSha256"]) is not None,
             "manifestSha256 must contain 64 hexadecimal digits")
    _text(ratings.get("listenerId"), "listenerId")
    _require(isinstance(key.get("provenance"), dict), "Missing provenance object")
    protocol = key.get("protocol")
    _require(isinstance(protocol, dict), "Missing fixed protocol")
    for name, expected in PROTOCOL.items():
        _require(protocol.get(name) == expected and type(protocol.get(name)) is type(expected),
                 f"Protocol field {name} differs from the preregistered v2 protocol")
    sessions = ratings.get("sessions")
    _require(isinstance(sessions, dict) and set(sessions) == set(PROTOCOL["sessionIds"]),
             "Exactly sessions s1 and s2 are required")
    times = {}
    for sid, session in sessions.items():
        _require(isinstance(session, dict), f"Invalid session {sid}")
        start = _time(session.get("startedAt"), f"{sid}.startedAt")
        end = _time(session.get("completedAt"), f"{sid}.completedAt")
        _require(start < end, f"Invalid time range for session {sid}")
        times[sid] = (start, end)
    _require(times["s1"][1] <= times["s2"][0] or times["s2"][1] <= times["s1"][0],
             "Listening sessions must not overlap")
    excerpts = key.get("excerpts")
    _require(isinstance(excerpts, list) and len(excerpts) > 0, "Missing excerpts")
    by_excerpt = {}
    for excerpt in excerpts:
        _require(isinstance(excerpt, dict), "Invalid excerpt")
        eid = _text(excerpt.get("id"), "excerpt.id")
        _require(eid not in by_excerpt, f"Duplicate excerpt id: {eid}")
        _text(excerpt.get("sourceId"), f"{eid}.sourceId")
        _text(excerpt.get("condition"), f"{eid}.condition")
        start = _number(excerpt.get("startSeconds"), f"{eid}.startSeconds", 0)
        end = _number(excerpt.get("endSeconds"), f"{eid}.endSeconds", 0)
        _require(end > start, f"Invalid excerpt interval: {eid}")
        _require(excerpt.get("split") in ("evaluation", "pilot"), f"Invalid excerpt split: {eid}")
        by_excerpt[eid] = excerpt
    trials = key.get("trials")
    _require(isinstance(trials, list) and len(trials) > 0, "Missing trials")
    values = ratings.get("scores")
    _require(isinstance(values, dict), "Missing scores object")
    trial_ids, cells = set(), {}
    for trial in trials:
        _require(isinstance(trial, dict), "Invalid trial")
        tid = _text(trial.get("id"), "trial.id")
        _require(tid not in trial_ids, f"Duplicate trial id: {tid}")
        trial_ids.add(tid)
        sid = _text(trial.get("sessionId"), f"{tid}.sessionId")
        eid = _text(trial.get("excerptId"), f"{tid}.excerptId")
        role = _text(trial.get("role"), f"{tid}.role")
        _require(sid in sessions and eid in by_excerpt and role in ROLES,
                 f"Invalid session, excerpt or role for {tid}")
        cell = (eid, sid, role)
        _require(cell not in cells, f"Duplicate role in excerpt/session: {cell}")
        item = values.get(tid)
        _require(isinstance(item, dict), f"Missing explicit rating for {tid}")
        value = _number(item.get("score"), f"{tid}.score", 0, 100)
        _require(item.get("playedA") is True and item.get("playedB") is True,
                 f"Both A and B must be played before rating {tid}")
        rated = _time(item.get("ratedAt"), f"{tid}.ratedAt")
        _require(times[sid][0] <= rated <= times[sid][1], f"Rating outside session: {tid}")
        cells[cell] = value
    _require(set(values) == trial_ids, "Missing or extra trial scores")
    _require(len(cells) == len(excerpts) * len(sessions) * len(ROLES),
             "Every excerpt needs all three roles in both sessions")
    return by_excerpt, cells


def _bootstrap(observations):
    import numpy as np
    from scipy.stats import bootstrap

    observations = np.asarray(observations, dtype=float)  # excerpt, session, role

    def statistic(indices, axis=-1):
        # All sessions and roles receive the SAME sampled excerpt indices.
        selected = observations[np.moveaxis(indices, axis, -1).astype(int)]
        med = np.median(selected, axis=(-3, -2))
        span = med[..., 1] - med[..., 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(span > 0, 100 * (med[..., 0] - med[..., 2]) / span, np.nan)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = bootstrap(
            (np.arange(len(observations)),), statistic, vectorized=True,
            paired=True, n_resamples=PROTOCOL["nResamples"], batch=256,
            confidence_level=PROTOCOL["confidenceLevel"], alternative="greater",
            method="percentile", random_state=np.random.default_rng(PROTOCOL["seed"]),
        )
    distribution = np.asarray(result.bootstrap_distribution)
    invalid = int(np.count_nonzero(~np.isfinite(distribution)))
    lower = float(result.confidence_interval.low)
    valid = invalid == 0 and math.isfinite(lower)
    return {
        "method": "SciPy paired excerpt-cluster percentile bootstrap; one-sided lower bound",
        "confidenceLevel": PROTOCOL["confidenceLevel"],
        "nResamples": PROTOCOL["nResamples"], "seed": PROTOCOL["seed"],
        "clusterUnit": "excerptId, preserving all roles and both sessions",
        "clusterCount": len(observations), "invalidResamples": invalid,
        "valid": valid, "rawLowerBoundPercent": lower if valid else None,
        "lowerBoundPercent": _display(lower) if valid else None,
    }


def score(key_path: Path, scores_path: Path) -> dict:
    key, ratings = _load(key_path), _load(scores_path)
    if "format" not in key:
        return _legacy(key, ratings)
    excerpts, cells = _validate(key, ratings)
    evaluation = [eid for eid, item in excerpts.items() if item["split"] == "evaluation"]
    used = evaluation or list(excerpts)  # pilot reports remain useful but inconclusive
    reasons = []
    if len(evaluation) < PROTOCOL["minDistinctExcerpts"]:
        reasons.append("At least 12 distinct evaluation excerpts are required; pilot data cannot meet the target.")
    intervals = defaultdict(list)
    pilot_intervals = defaultdict(list)
    for item in excerpts.values():
        if item["split"] == "pilot":
            pilot_intervals[item["sourceId"]].append((item["startSeconds"], item["endSeconds"]))
    for eid in evaluation:
        item = excerpts[eid]
        if item["endSeconds"] - item["startSeconds"] < 3:
            reasons.append(f"Evaluation excerpt {eid} is shorter than 3 seconds.")
        intervals[item["sourceId"]].append((item["startSeconds"], item["endSeconds"], eid))
        if any(max(start, item["startSeconds"]) < min(end, item["endSeconds"]) - 1e-9
               for start, end in pilot_intervals[item["sourceId"]]):
            reasons.append(f"Evaluation excerpt {eid} overlaps pilot material from the same source.")
    for source, ranges in intervals.items():
        ranges.sort()
        latest_end = -1.0
        for start, end, eid in ranges:
            if start < latest_end - 1e-9:
                reasons.append(f"Evaluation excerpt {eid} overlaps another excerpt from {source}.")
            latest_end = max(latest_end, end)
    eligibility_reasons = list(reasons)
    medians = {role: statistics.median(cells[eid, sid, role] for eid in used
                                      for sid in PROTOCOL["sessionIds"]) for role in ROLES}
    controls = {}
    for sid in PROTOCOL["sessionIds"]:
        ref = statistics.median(cells[eid, sid, "reference"] for eid in used)
        anchor = statistics.median(cells[eid, sid, "anchor"] for eid in used)
        controls[sid] = {"referenceMedian": ref, "anchorMedian": anchor,
                         "span": ref - anchor, "valid": ref >= 90 and ref - anchor >= 20}
        if not controls[sid]["valid"]:
            reasons.append(f"Session {sid} fails hidden reference or anchor controls.")
    raw = _normalized(medians)
    if raw is None:
        reasons.append("Pooled normalization denominator is not positive.")
    observations = [[[cells[eid, sid, role] for role in ROLES]
                     for sid in PROTOCOL["sessionIds"]] for eid in used]
    if len(used) >= 2:
        uncertainty = _bootstrap(observations)
    else:
        uncertainty = {"valid": False, "rawLowerBoundPercent": None,
                       "lowerBoundPercent": None, "clusterCount": len(used),
                       "invalidResamples": None, "nResamples": 0}
    if not uncertainty["valid"]:
        reasons.append("Bootstrap interval is invalid, has nonpositive resampled denominators, or lacks clusters.")
    conclusive = not reasons
    target = conclusive and uncertainty["rawLowerBoundPercent"] >= PROTOCOL["requiredPercent"]
    return {
        "format": "open-dehiss-blind-report-v2", "studyId": key["studyId"],
        "manifestSha256": key["manifestSha256"], "listenerId": ratings["listenerId"],
        "protocol": key["protocol"], "provenance": key["provenance"],
        "method": "100 * (median(candidate) - median(anchor)) / (median(reference) - median(anchor))",
        "medians": medians, "rawNormalizedSimilarityPercent": raw,
        "normalizedSimilarityPercent": _display(raw), "requiredPercent": 9,
        "validScale": all(item["valid"] for item in controls.values()),
        "controlsBySession": controls, "uncertainty": uncertainty,
        "eligibility": {"evaluationExcerptCount": len(evaluation), "scoredExcerptCount": len(used),
                        "minimumDistinctExcerpts": 12, "eligible": not eligibility_reasons,
                        "reasons": eligibility_reasons},
        "targetReached": target, "status": "conclusive" if conclusive else "inconclusive",
        "decision": ("met" if target else "not_met") if conclusive else "inconclusive",
        "reasons": reasons, "limitations": LIMITATIONS,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", type=Path)
    parser.add_argument("scores", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = score(args.key, args.scores)
        payload = json.dumps(result, indent=2, allow_nan=False)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(payload + "\n")
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"Scoring failed: {exc}\n")
    print(payload)
    return 0 if result["targetReached"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
