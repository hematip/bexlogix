"""Regression tests for the sample data generator.

The generator is the seed source for fresh deployments and demos, so the
shape and geographic placement of its output must stay stable.
"""

from __future__ import annotations

from datetime import date

import pytest

from server.app.utils.tehran_geo import (
    REGION_TO_DISTRICTS,
    TEHRAN_DISTRICT_CENTROIDS,
)
from server.db.generate_sample_files import (
    STORE_COUNT,
    VISITOR_COUNT,
    _build_daily_status,
    _build_stores,
)


class TestSampleStores:
    def test_count_matches_constant(self):
        df = _build_stores()
        assert len(df) == STORE_COUNT

    def test_all_stores_lie_inside_tehran_bbox(self):
        df = _build_stores()
        # Tehran proper sits inside this box; anything outside is a sign the
        # generator slipped back to the old uniform-random scheme.
        assert df["lat"].min() >= 35.55
        assert df["lat"].max() <= 35.85
        assert df["lon"].min() >= 51.15
        assert df["lon"].max() <= 51.60

    def test_region_to_geography_alignment(self):
        """A store labelled شمال must sit in northern Tehran, etc."""
        df = _build_stores()
        means = df.groupby("region")[["lat", "lon"]].mean()
        # شمال must have the highest mean lat, جنوب the lowest.
        assert means.loc["شمال", "lat"] > means.loc["جنوب", "lat"]
        # شرق must have higher lon than غرب.
        assert means.loc["شرق", "lon"] > means.loc["غرب", "lon"]

    def test_region_balance_is_preserved(self):
        df = _build_stores()
        counts = df["region"].value_counts()
        assert set(counts.index) == set(REGION_TO_DISTRICTS.keys())
        # Every region should get roughly STORE_COUNT / 5 stores.
        for r, n in counts.items():
            assert n == STORE_COUNT // len(REGION_TO_DISTRICTS)

    def test_at_least_one_active_category_per_store(self):
        df = _build_stores()
        any_active = (
            df["has_confectionery"]
            | df["has_oil"]
            | df["has_pasta"]
        )
        assert any_active.all()


class TestVisitorSeed:
    def test_visitor_starts_are_well_spread(self):
        df = _build_daily_status(date(2026, 5, 15).isoformat())
        assert len(df) == VISITOR_COUNT
        # Lat span across visitors must cover at least ~15 km so the
        # capacitated k-means clustering has something to anchor on.
        lat_span_km = (df["start_lat"].max() - df["start_lat"].min()) * 111
        lon_span_km = (df["start_lon"].max() - df["start_lon"].min()) * 88
        assert lat_span_km > 15, f"lat span {lat_span_km:.1f}km too narrow"
        assert lon_span_km > 15, f"lon span {lon_span_km:.1f}km too narrow"

    def test_visitor_starts_are_known_district_centroids(self):
        df = _build_daily_status(date(2026, 5, 15).isoformat())
        all_centroids = set(TEHRAN_DISTRICT_CENTROIDS.values())
        for _, row in df.iterrows():
            assert (
                round(row["start_lat"], 3),
                round(row["start_lon"], 3),
            ) in {(round(lat, 3), round(lon, 3)) for lat, lon in all_centroids}
