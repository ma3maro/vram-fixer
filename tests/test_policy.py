"""Regression tests: wrong importance direction, under-resolution, or over-decimation."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'vram_fixer' / 'policy.py'
spec = importlib.util.spec_from_file_location('policy', path)
policy = importlib.util.module_from_spec(spec)
if path.exists():
    spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def test_reference_and_larger_are_not_reduced(self):
        for span in (400, 800):
            self.assertEqual(policy.importance(span, 400), 1.0)
            self.assertEqual(policy.mesh_ratio(100000, span, span, 400), 1.0)

    def test_importance_is_monotone_and_never_zero(self):
        values = [policy.importance(s, 400) for s in (0, 10, 40, 100, 200, 400)]
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[0], 0)

    def test_texture_never_upsizes_or_changes_aspect(self):
        self.assertEqual(policy.texture_size(4096, 2048, 650), (768, 384))
        self.assertEqual(policy.texture_size(512, 256, 900), (512, 256))
        self.assertEqual(policy.texture_size(4096, 1024, 1500), (1536, 384))

    def test_texture_budget_respects_projected_uv_demand(self):
        low = policy.texture_demand(100, .1, 400, detail=False)
        detail = policy.texture_demand(100, .1, 400, detail=True)
        self.assertGreaterEqual(low, 1000)
        self.assertGreater(detail, low)
        self.assertGreater(policy.texture_demand(200, .1, 400), low)

    def test_mesh_budget_reduces_dense_small_not_sparse(self):
        self.assertLess(policy.mesh_ratio(100000, 60, 60, 400), .5)
        self.assertEqual(policy.mesh_ratio(100, 60, 60, 400), 1.0)
        small = policy.mesh_ratio(100000, 60, 60, 400)
        medium = policy.mesh_ratio(100000, 200, 200, 400)
        self.assertGreater(medium, small)
        self.assertGreaterEqual(small, .08)

    def test_careful_preserves_more_than_strong(self):
        self.assertGreater(policy.mesh_ratio(100000, 80, 80, 400, 'CAREFUL'),
                           policy.mesh_ratio(100000, 80, 80, 400, 'STRONG'))
        self.assertGreater(policy.texture_demand(80, .2, 400, preset='CAREFUL'),
                           policy.texture_demand(80, .2, 400, preset='STRONG'))

    def test_uv_outliers_are_weighted_by_screen_coverage(self):
        values = [(800, 9999), (8000, 1)]
        self.assertEqual(policy.coverage_demand(values, 'CAREFUL'), 800)
        self.assertEqual(policy.coverage_demand([(8000, 100)], 'STRONG'), 8000)

    def test_invalid_inputs_fail_closed(self):
        self.assertEqual(policy.mesh_ratio(100, 0, 0, 0), 1)
        with self.assertRaises(ValueError):
            policy.texture_size(0, 10, 20)


if __name__ == '__main__':
    unittest.main()
