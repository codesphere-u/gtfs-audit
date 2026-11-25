"""CLI for gtfs-audit."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from gtfs_audit.validator import GtfsStop, GtfsStopTime, audit_gtfs_feed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gtfs-audit",
        description="GTFS & informal paratransit feed validator & headway bunching analyzer.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Audit a sample Kampala Pioneer/Matatu corridor GTFS feed")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        stops = [
            GtfsStop("KLA-OLD", "Old Taxi Park", 0.3136, 32.5758),
            GtfsStop("KLA-WAN", "Wandegeya Stage", 0.3316, 32.5714),
            GtfsStop("KLA-NTN", "Ntinda Stage", 0.3541, 32.6126),
        ]
        stop_times = [
            GtfsStopTime("T1", "R-NTINDA", "KLA-OLD", 1, "07:00:00", "07:00:00"),
            GtfsStopTime("T1", "R-NTINDA", "KLA-WAN", 2, "07:10:00", "07:11:00"),
            GtfsStopTime("T1", "R-NTINDA", "KLA-NTN", 3, "07:28:00", "07:28:00"),
            GtfsStopTime("T2", "R-NTINDA", "KLA-OLD", 1, "07:15:00", "07:15:00"),
            GtfsStopTime("T2", "R-NTINDA", "KLA-WAN", 2, "07:25:00", "07:26:00"),
            GtfsStopTime("T2", "R-NTINDA", "KLA-NTN", 3, "07:43:00", "07:43:00"),
            GtfsStopTime("T3", "R-NTINDA", "KLA-OLD", 1, "07:30:00", "07:30:00"),
            GtfsStopTime("T3", "R-NTINDA", "KLA-WAN", 2, "07:40:00", "07:41:00"),
            GtfsStopTime("T3", "R-NTINDA", "KLA-NTN", 3, "07:58:00", "07:58:00"),
        ]
        rep = audit_gtfs_feed(stops, stop_times)
        print(
            json.dumps(
                {
                    "passed": rep.passed,
                    "stops_count": rep.stops_count,
                    "trips_count": rep.trips_count,
                    "route_metrics": [
                        {
                            "route_id": m.route_id,
                            "mean_headway_min": m.mean_headway_min,
                            "headway_cv": m.headway_cv,
                            "bunched_departures": m.bunched_departures,
                        }
                        for m in rep.route_metrics
                    ],
                    "findings": [
                        {"rule_id": f.rule_id, "severity": f.severity, "message": f.message}
                        for f in rep.findings
                    ],
                },
                indent=2,
            )
        )
        return 0 if rep.passed else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
