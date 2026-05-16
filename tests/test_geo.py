"""Tests for the geographic utility module."""

from __future__ import annotations

import math

import pytest

from server.app.utils.geo import cumulative_path_distance_km, haversine_km


class TestHaversineKm:
    def test_zero_distance_for_identical_points(self):
        assert haversine_km(35.7, 51.3, 35.7, 51.3) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_tehran_north_to_south(self):
        # ~5 km north-south corridor inside Tehran.
        d = haversine_km(35.75, 51.40, 35.70, 51.40)
        assert d == pytest.approx(5.56, rel=0.02)

    def test_symmetry(self):
        forward = haversine_km(35.70, 51.30, 35.80, 51.40)
        backward = haversine_km(35.80, 51.40, 35.70, 51.30)
        assert forward == pytest.approx(backward, abs=1e-9)

    def test_non_negative(self):
        for a in [-90, -45, 0, 45, 90]:
            for b in [-180, -90, 0, 90, 179]:
                assert haversine_km(a, b, a + 0.1, b + 0.1) >= 0


class TestCumulativePathDistanceKm:
    def test_empty_returns_empty(self):
        assert cumulative_path_distance_km(35.7, 51.3, []) == []

    def test_missing_start_returns_empty(self):
        assert cumulative_path_distance_km(None, 51.3, [(35.7, 51.3)]) == []
        assert cumulative_path_distance_km(35.7, None, [(35.7, 51.3)]) == []

    def test_cumulative_is_monotonic_increasing(self):
        cumulative = cumulative_path_distance_km(
            35.70,
            51.30,
            [(35.71, 51.31), (35.72, 51.32), (35.73, 51.33)],
        )
        assert len(cumulative) == 3
        for prev, curr in zip(cumulative, cumulative[1:]):
            assert curr >= prev

    def test_single_step_matches_haversine(self):
        cumulative = cumulative_path_distance_km(35.70, 51.30, [(35.71, 51.31)])
        direct = haversine_km(35.70, 51.30, 35.71, 51.31)
        assert cumulative[0] == pytest.approx(round(direct, 3), abs=1e-3)

    def test_finite_for_far_apart_points(self):
        cumulative = cumulative_path_distance_km(0.0, 0.0, [(0.0, 180.0)])
        assert math.isfinite(cumulative[0])
        assert cumulative[0] > 0
