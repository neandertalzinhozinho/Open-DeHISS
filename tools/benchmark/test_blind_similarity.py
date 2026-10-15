"""Synthetic ratings exercise the scorer only; these are not listening results."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from score_blind_similarity import PROTOCOL, ROLES, score


def fixture(count=12, candidate=50, reference=100, anchor=0):
    key = {"format": "open-dehiss-blind-key-v2", "studyId": "synthetic-unit-test",
           "manifestSha256": "a" * 64, "protocol": copy.deepcopy(PROTOCOL),
           "provenance": {"purpose": "synthetic unit tests, never perceptual evidence"},
           "excerpts": [], "trials": []}
    scores = {"format": "open-dehiss-blind-scores-v2", "studyId": key["studyId"],
              "manifestSha256": key["manifestSha256"], "listenerId": "SYNTHETIC",
              "sessions": {}, "scores": {}}
    for session_number, sid in enumerate(PROTOCOL["sessionIds"], 1):
        scores["sessions"][sid] = {
            "startedAt": f"2026-10-13T0{session_number}:00:00Z",
            "completedAt": f"2026-10-13T0{session_number}:30:00Z",
        }
        for n in range(count):
            eid = f"e{n:02d}"
            if session_number == 1:
                key["excerpts"].append({"id": eid, "sourceId": "voice",
                    "startSeconds": n * 4, "endSeconds": n * 4 + 4,
                    "condition": ("original", "hiss", "variable")[n % 3], "split": "evaluation"})
            for role, value in (("candidate", candidate), ("reference", reference), ("anchor", anchor)):
                tid = f"{sid}-{eid}-{role}"
                key["trials"].append({"id": tid, "sessionId": sid, "excerptId": eid, "role": role})
                scores["scores"][tid] = {"score": value, "playedA": True, "playedB": True,
                    "ratedAt": f"2026-10-13T0{session_number}:15:00Z"}
    return key, scores


class BlindSimilarityTests(unittest.TestCase):
    def run_score(self, key, ratings):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "key.json").write_text(json.dumps(key), encoding="utf-8")
            (root / "scores.json").write_text(json.dumps(ratings), encoding="utf-8")
            result = score(root / "key.json", root / "scores.json")
            json.dumps(result, allow_nan=False)
            return result

    def test_legacy_cannot_claim_target_even_when_high(self):
        result = self.run_score({"1": "reference", "2": "anchor", "3": "candidate"},
                                {"scores": {"1": 90, "2": 10, "3": 90}})
        self.assertEqual(result["normalizedSimilarityPercent"], 100)
        self.assertFalse(result["targetReached"])
        self.assertEqual(result["status"], "inconclusive")

    def test_below_at_and_above_nine_percent(self):
        for value, target in ((8.99, False), (9, True), (9.01, True)):
            with self.subTest(value=value):
                result = self.run_score(*fixture(candidate=value))
                self.assertEqual(result["targetReached"], target)
                self.assertEqual(result["status"], "conclusive")
                self.assertAlmostEqual(result["uncertainty"]["rawLowerBoundPercent"], value)

    def test_identity_reference_has_valid_degenerate_interval(self):
        result = self.run_score(*fixture(candidate=100))
        self.assertTrue(result["uncertainty"]["valid"])
        self.assertEqual(result["uncertainty"]["rawLowerBoundPercent"], 100)
        self.assertTrue(result["targetReached"])

    def test_high_point_estimate_fails_when_lower_bound_below_target(self):
        key, ratings = fixture(candidate=20)
        for sid in PROTOCOL["sessionIds"]:
            for n in range(5):
                ratings["scores"][f"{sid}-e{n:02d}-candidate"]["score"] = 0
        result = self.run_score(key, ratings)
        self.assertEqual(result["rawNormalizedSimilarityPercent"], 20)
        self.assertEqual(result["uncertainty"]["rawLowerBoundPercent"], 0)
        self.assertFalse(result["targetReached"])
        self.assertEqual(result["decision"], "not_met")

    def test_session_control_failure_cannot_approve(self):
        for role, value in (("reference", 89), ("anchor", 81)):
            with self.subTest(role=role):
                key, ratings = fixture(candidate=100)
                for n in range(12):
                    ratings["scores"][f"s2-e{n:02d}-{role}"]["score"] = value
                result = self.run_score(key, ratings)
                self.assertGreaterEqual(result["normalizedSimilarityPercent"], 9)
                self.assertFalse(result["validScale"])
                self.assertFalse(result["targetReached"])
                self.assertEqual(result["status"], "inconclusive")

    def test_raw_result_not_clipped_for_inference(self):
        for candidate, expected in ((0, -12.5), (100, 112.5)):
            result = self.run_score(*fixture(candidate=candidate, reference=90, anchor=10))
            self.assertEqual(result["rawNormalizedSimilarityPercent"], expected)
            self.assertEqual(result["uncertainty"]["rawLowerBoundPercent"], expected)
            self.assertEqual(result["normalizedSimilarityPercent"], max(0, min(100, expected)))

    def test_reject_non_numeric_nonfinite_and_out_of_range_scores(self):
        for value in (None, True, False, "50", float("nan"), float("inf"), -0.1, 100.1):
            with self.subTest(value=value):
                key, ratings = fixture()
                ratings["scores"]["s1-e00-candidate"]["score"] = value
                with self.assertRaises(ValueError):
                    self.run_score(key, ratings)

    def test_missing_or_extra_scores_rejected(self):
        for extra in (False, True):
            key, ratings = fixture()
            if extra:
                ratings["scores"]["unexpected"] = ratings["scores"]["s1-e00-candidate"]
            else:
                ratings["scores"].pop("s1-e00-candidate")
            with self.assertRaises(ValueError):
                self.run_score(key, ratings)

    def test_playback_required_and_truthy_values_do_not_count(self):
        for field in ("playedA", "playedB"):
            for value in (False, None, 1, "true"):
                key, ratings = fixture()
                ratings["scores"]["s1-e00-candidate"][field] = value
                with self.assertRaises(ValueError):
                    self.run_score(key, ratings)

    def test_explicit_timestamp_inside_session_required(self):
        for value in (None, "nonsense", "2026-10-13T01:15:00", "2026-10-13T05:15:00Z"):
            key, ratings = fixture()
            ratings["scores"]["s1-e00-candidate"]["ratedAt"] = value
            with self.assertRaises(ValueError):
                self.run_score(key, ratings)

    def test_sessions_must_be_complete_and_nonoverlapping(self):
        key, ratings = fixture()
        ratings["sessions"]["s2"] = ratings["sessions"]["s1"].copy()
        with self.assertRaises(ValueError):
            self.run_score(key, ratings)
        key, ratings = fixture()
        del ratings["sessions"]["s2"]["completedAt"]
        with self.assertRaises(ValueError):
            self.run_score(key, ratings)

    def test_duplicate_trials_excerpts_and_roles_rejected(self):
        for kind in ("trial", "excerpt", "role"):
            key, ratings = fixture()
            if kind == "trial":
                key["trials"].append(key["trials"][0].copy())
            elif kind == "excerpt":
                key["excerpts"].append(key["excerpts"][0].copy())
            else:
                key["trials"][0]["role"] = key["trials"][1]["role"]
            with self.assertRaises(ValueError):
                self.run_score(key, ratings)

    def test_unbalanced_roles_rejected(self):
        key, ratings = fixture()
        trial = key["trials"].pop()
        ratings["scores"].pop(trial["id"])
        with self.assertRaises(ValueError):
            self.run_score(key, ratings)

    def test_duplicate_json_fields_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            key = Path(d) / "key.json"
            key.write_text('{"1":"reference","1":"anchor"}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                score(key, key)

    def test_protocol_and_provenance_identity_cannot_change(self):
        for field in ("studyId", "manifestSha256", "listenerId"):
            key, ratings = fixture()
            ratings[field] = ""
            with self.assertRaises(ValueError):
                self.run_score(key, ratings)
        for field, value in (("requiredPercent", 8), ("confidenceLevel", 0.80),
                             ("nResamples", 99), ("minDistinctExcerpts", 4), ("seed", 0)):
            key, ratings = fixture()
            key["protocol"][field] = value
            with self.assertRaises(ValueError):
                self.run_score(key, ratings)

    def test_insufficient_short_and_overlapping_material_inconclusive(self):
        for condition in ("too_few", "short", "overlap", "nested_overlap"):
            key, ratings = fixture(count=11 if condition == "too_few" else 12)
            if condition == "short":
                key["excerpts"][0]["endSeconds"] = 2.9
            elif condition == "overlap":
                key["excerpts"][1]["startSeconds"] = 3.9
            elif condition == "nested_overlap":
                key["excerpts"][0]["endSeconds"] = 12
            result = self.run_score(key, ratings)
            self.assertFalse(result["eligibility"]["eligible"])
            self.assertFalse(result["targetReached"])
            self.assertEqual(result["status"], "inconclusive")

    def test_pilot_can_be_scored_descriptively_but_never_approved(self):
        key, ratings = fixture(count=4)
        for excerpt in key["excerpts"]:
            excerpt.update(split="pilot", startSeconds=1.5, endSeconds=9.5)
        result = self.run_score(key, ratings)
        self.assertEqual(result["normalizedSimilarityPercent"], 50)
        self.assertEqual(result["eligibility"]["evaluationExcerptCount"], 0)
        self.assertFalse(result["targetReached"])

    def test_evaluation_cannot_reuse_pilot_material(self):
        key, ratings = fixture(count=13)
        key["excerpts"][0]["split"] = "pilot"
        key["excerpts"][1].update(startSeconds=0, endSeconds=4)
        result = self.run_score(key, ratings)
        self.assertEqual(result["eligibility"]["evaluationExcerptCount"], 12)
        self.assertFalse(result["targetReached"])
        self.assertTrue(any("overlaps pilot" in reason for reason in result["reasons"]))

    def test_nonpositive_bootstrap_denominator_fails_closed(self):
        key, ratings = fixture()
        # Pooled controls pass, but samples dominated by five collapsed excerpts
        # have zero denominator. Never silently drop those replicates.
        for sid in PROTOCOL["sessionIds"]:
            for n in range(5):
                ratings["scores"][f"{sid}-e{n:02d}-anchor"]["score"] = 100
        result = self.run_score(key, ratings)
        self.assertTrue(result["validScale"])
        self.assertGreater(result["uncertainty"]["invalidResamples"], 0)
        self.assertIsNone(result["uncertainty"]["rawLowerBoundPercent"])
        self.assertFalse(result["targetReached"])

    def test_paired_bootstrap_retains_roles_and_sessions_reproducibly(self):
        import numpy as np
        key, ratings = fixture()
        matrix = []
        for n in range(12):
            sessions = []
            for j, sid in enumerate(PROTOCOL["sessionIds"]):
                anchor, ref = n * 2 + j, 100
                candidate = 0.5 * (anchor + ref)
                sessions.append([candidate, ref, anchor])
                for role, value in zip(ROLES, sessions[-1]):
                    ratings["scores"][f"{sid}-e{n:02d}-{role}"]["score"] = value
            matrix.append(sessions)
        first = self.run_score(key, ratings)
        second = self.run_score(key, ratings)
        self.assertEqual(first["uncertainty"], second["uncertainty"])
        self.assertEqual(first["uncertainty"]["clusterCount"], 12)
        self.assertAlmostEqual(first["uncertainty"]["rawLowerBoundPercent"], 50)
        # Independent reference implementation resamples all six observations as
        # one block; compare its 5th percentile to the SciPy implementation.
        rng = np.random.default_rng(PROTOCOL["seed"])
        indices = rng.integers(0, 12, size=(PROTOCOL["nResamples"], 12))
        med = np.median(np.asarray(matrix)[indices], axis=(1, 2))
        samples = 100 * (med[:, 0] - med[:, 2]) / (med[:, 1] - med[:, 2])
        self.assertAlmostEqual(first["uncertainty"]["rawLowerBoundPercent"], np.quantile(samples, 0.05))

    def test_cli_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "key.json").write_text(json.dumps({"a": "anchor", "r": "reference", "c": "candidate"}))
            (root / "scores.json").write_text(json.dumps({"scores": {"a": 0, "r": 100, "c": 50}}))
            output = root / "report.json"
            output.write_text("preserve this")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("score_blind_similarity.py")),
                                     str(root / "key.json"), str(root / "scores.json"), str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_text(), "preserve this")


if __name__ == "__main__":
    unittest.main(verbosity=2)
