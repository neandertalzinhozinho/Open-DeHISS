"""Synthetic diagnostic controls; never presented as voice/listener evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from score_processing_effect import align_render, compare_aligned, evaluate


class ProcessingEffectTests(unittest.TestCase):
    def setUp(self):
        self.rate = 16000
        self.x = np.random.default_rng(71).normal(0, .1, (2 * self.rate, 2))

    def result(self, reference, candidate, x=None):
        return compare_aligned(self.x if x is None else x, reference, candidate,
                               self.rate, start_seconds=0)

    @staticmethod
    def focus(report):
        return [r for r in report["summaries"] if r["bandHz"] == [800, 6000]]

    def test_identical_effect_zero_error_and_projection_one(self):
        report = self.result(.5 * self.x, .5 * self.x)
        for row in self.focus(report):
            self.assertEqual(row["normalizedEffectError"], 0)
            self.assertEqual(row["materialReferenceWindows"], 2)
        for row in report["windows"]:
            self.assertEqual(row["normalizedEffectError"], 0)
            self.assertAlmostEqual(row["effectProjectionOnReference"], 1)
            self.assertAlmostEqual(row["effectCosine"], 1)

    def test_dry_candidate_has_error_one_never_identity(self):
        report = self.result(.5 * self.x, self.x)
        for row in self.focus(report):
            self.assertEqual(row["normalizedEffectError"], 1)
            self.assertEqual(row["materialCandidateWindows"], 0)
            self.assertEqual(row["materialReferenceButCandidateBelowThresholdWindows"], 2)
        for row in report["windows"]:
            self.assertEqual(row["effectProjectionOnReference"], 0)
            self.assertIsNone(row["effectCosine"])

    def test_inactive_reference_is_inconclusive_even_for_identical_outputs(self):
        for candidate in (self.x, .5 * self.x):
            for row in self.focus(self.result(self.x, candidate)):
                self.assertIsNone(row["normalizedEffectError"])
                self.assertIsNone(row["dryControlNormalizedEffectError"])
                self.assertEqual(row["materialReferenceWindows"], 0)
                self.assertEqual(row["status"], "inconclusive_no_material_reference_effect")

    def test_almost_transparent_reference_does_not_satisfy_material_threshold(self):
        for row in self.focus(self.result(.99 * self.x, .99 * self.x)):
            self.assertIsNone(row["normalizedEffectError"])

    def test_silent_or_below_floor_input_is_inconclusive(self):
        for x in (np.zeros_like(self.x), self.x * 1e-7):
            for row in self.focus(self.result(.5 * x, .5 * x, x)):
                self.assertEqual(row["materialReferenceWindows"], 0)
                self.assertIsNone(row["normalizedEffectError"])

    def test_phase_inversion_penalized_despite_identical_magnitudes(self):
        report = self.result(.5 * self.x, -.5 * self.x)
        for row in self.focus(report):
            self.assertAlmostEqual(row["normalizedEffectError"], 4)
            self.assertAlmostEqual(row["medianCandidateMinusReferenceOutputDb"], 0)

    def test_phase_only_reference_is_change_not_attenuation(self):
        for row in self.focus(self.result(-self.x, -self.x)):
            self.assertEqual(row["normalizedEffectError"], 0)
            self.assertEqual(row["materialReferenceWindows"], 2)
            self.assertEqual(row["referenceAttenuatingAtLeast1DbWindows"], 0)

    def test_gain_difference_preserved_not_fitted_away(self):
        report = self.result(.5 * self.x, .75 * self.x)
        for row in self.focus(report):
            self.assertAlmostEqual(row["normalizedEffectError"], .25)
            self.assertAlmostEqual(row["medianCandidateMinusReferenceOutputDb"],
                                   20 * np.log10(1.5), places=10)
        for row in report["windows"]:
            self.assertAlmostEqual(row["effectProjectionOnReference"], .5)

    def test_channels_retained_separately(self):
        candidate = .5 * self.x
        candidate[:, 1] = self.x[:, 1]
        rows = self.focus(self.result(.5 * self.x, candidate))
        self.assertEqual([r["normalizedEffectError"] for r in rows], [0, 1])

    def test_reference_inactivity_excluded_from_denominator(self):
        reference = self.x.copy()
        reference[self.rate:] *= .5
        report = self.result(reference, self.x)
        for row in self.focus(report):
            self.assertEqual(row["windows"], 2)
            self.assertEqual(row["materialReferenceWindows"], 1)
            self.assertEqual(row["normalizedEffectError"], 1)

    def test_default_start_and_partial_tail_are_explicit(self):
        x = np.concatenate([self.x, self.x[:self.rate // 3]])
        report = compare_aligned(x, .5 * x, .5 * x, self.rate)
        self.assertEqual(report["windows"][0]["startSeconds"], 1.5)
        self.assertAlmostEqual(report["windows"][0]["endSeconds"], len(x) / self.rate)
        self.assertLess(report["windows"][0]["durationSeconds"], 1)

    def test_invalid_arrays_rates_and_analysis_start_rejected(self):
        for bad in (self.x[:, 0], self.x[:10], self.x[:, :0], self.x * np.nan, self.x * np.inf):
            with self.assertRaises(ValueError):
                self.result(bad, self.x)
        for rate in (0, 8000, True, 16000.5):
            with self.assertRaises(ValueError):
                compare_aligned(self.x, self.x, self.x, rate, 0)
        for start in (-1, np.nan, np.inf, True, 2):
            with self.assertRaises(ValueError):
                compare_aligned(self.x, self.x, self.x, self.rate, start)

    def test_json_is_finite_even_with_zero_signals(self):
        for x in (self.x, np.zeros_like(self.x)):
            json.dumps(self.result(.5 * x, np.zeros_like(x), x), allow_nan=False)

    def test_finite_input_that_overflows_analysis_is_rejected(self):
        huge = self.x * 1e200
        with self.assertRaisesRegex(ValueError, "Nonfinite analysis"):
            self.result(.5 * huge, huge, huge)

    def test_delay_audit_accepts_known_delay_and_preserves_gain(self):
        delayed = np.pad(.5 * self.x, ((37, 37), (0, 0)))
        aligned, measured = align_render(self.x, delayed, 37)
        self.assertEqual(measured, [37, 37])
        np.testing.assert_array_equal(aligned, .5 * self.x)

    def test_wrong_negative_or_incomplete_alignment_rejected(self):
        delayed = np.pad(.5 * self.x, ((37, 37), (0, 0)))
        for delay in (-1, 32769, 37.0, True, 20):
            with self.assertRaises(ValueError):
                align_render(self.x, delayed, delay)
        with self.assertRaisesRegex(ValueError, "Missing processed tail"):
            align_render(self.x, delayed[:len(self.x) + 36], 37)

    def test_one_sample_alignment_disagreement_is_rejected(self):
        delayed = np.pad(.5 * self.x, ((37, 37), (0, 0)))
        for logged in (36, 38):
            with self.assertRaisesRegex(ValueError, 'Exact integer alignment required'):
                align_render(self.x, delayed, logged)

    def test_each_window_tail_cannot_hide_processing_error(self):
        reference = .5 * self.x
        candidate = reference.copy()
        # At16k, unpadded 2048/1024 STFT used to drop these640samples.
        for end in (self.rate, 2 * self.rate):
            candidate[end - 640:end] = self.x[end - 640:end]
        report = self.result(reference, candidate)
        for row in self.focus(report):
            self.assertGreater(row['normalizedEffectError'], .005)
        for row in report['windows']:
            self.assertFalse(row['exactEffectMatch'])
        self.assertEqual(report['analysisRevision'], 2)

    def test_existing_provenance_audit_is_mandatory(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("score_processing_effect.validate_objective_evidence",
                       side_effect=ValueError("tampered render")) as audit:
                with self.assertRaisesRegex(ValueError, "tampered render"):
                    evaluate(Path(folder))
                audit.assert_called_once_with(Path(folder).resolve())


if __name__ == "__main__":
    unittest.main()
