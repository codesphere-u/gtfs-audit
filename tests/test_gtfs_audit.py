"""Tests for GTFS stop/time validation, Haversine speed checks, headway bunching & CLI."""

from __future__ import annotations

import json

import pytest

from gtfs_audit import GtfsStop, GtfsStopTime, audit_gtfs_feed, parse_gtfs_seconds
from gtfs_audit.cli import main as cli_main


def test_catches_null_island_missing_stop_teleportation_and_bunching() -> None:
    assert parse_gtfs_seconds("25:30:00") == 25 * 3600 + 1800

    stops = [
        GtfsStop("S1", "Town", 0.3136, 32.5758),
        GtfsStop("S2", "Airport", 0.0424, 32.4435),  # ~33 km away
        GtfsStop("BAD", "Null Island", 0.0, 0.0),
    ]
    times = [
        # Teleport 33km in 0 seconds + missing stop reference
        GtfsStopTime("T1", "R1", "S1", 1, "08:00:00", "08:00:00"),
        GtfsStopTime("T1", "R1", "S2", 2, "08:00:00", "08:00:00"),
        GtfsStopTime("T1", "R1", "GHOST", 3, "08:10:00", "08:10:00"),
        # Severe bus bunching: 08:00, 08:01, 08:45
        GtfsStopTime("T2", "R1", "S1", 1, "08:01:00", "08:01:00"),
        GtfsStopTime("T3", "R1", "S1", 1, "08:45:00", "08:45:00"),
    ]
    rep = audit_gtfs_feed(stops, times)
    assert rep.passed is False
    rules = {f.rule_id for f in rep.findings}
    assert {"GTFS-001", "GTFS-002", "GTFS-005", "GTFS-006"}.issubset(rules)
    assert rep.route_metrics[0].bunched_departures >= 1


def test_cli_demo(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["demo"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is True
    assert out["route_metrics"][0]["mean_headway_min"] == 15.0
    assert out["route_metrics"][0]["headway_cv"] == 0.0
