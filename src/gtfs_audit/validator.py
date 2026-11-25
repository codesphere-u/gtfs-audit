"""GTFS & informal paratransit validator, Haversine speed audit & headway bunching analyzer."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class GtfsStop:
    stop_id: str
    stop_name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class GtfsStopTime:
    trip_id: str
    route_id: str
    stop_id: str
    stop_sequence: int
    arrival_time: str  # HH:MM:SS (GTFS allows >24:00:00 for post-midnight trips)
    departure_time: str


@dataclass(frozen=True)
class GtfsFinding:
    rule_id: str
    severity: str  # error | warning
    entity_id: str
    message: str


@dataclass(frozen=True)
class RouteHeadwayMetrics:
    route_id: str
    trips_count: int
    mean_headway_min: float
    headway_cv: float  # Coefficient of variation (0 = perfectly regular; >0.40 = severe bunching)
    bunched_departures: int  # Departures spaced < 50% of mean headway
    service_span_hours: float


@dataclass(frozen=True)
class GtfsAuditReport:
    stops_count: int
    trips_count: int
    passed: bool
    error_count: int
    warning_count: int
    route_metrics: tuple[RouteHeadwayMetrics, ...]
    findings: tuple[GtfsFinding, ...]


def parse_gtfs_seconds(hms: str) -> int:
    """Parse GTFS `HH:MM:SS` timestamp (supporting hours >= 24) into seconds since service midnight."""
    parts = hms.strip().split(":")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid GTFS HH:MM:SS time '{hms}'")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    if not (0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError(f"Invalid minutes/seconds in GTFS time '{hms}'")
    return h * 3600 + m * 60 + s


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def audit_gtfs_feed(
    stops: list[GtfsStop],
    stop_times: list[GtfsStopTime],
    *,
    max_plausible_speed_kmh: float = 110.0,
) -> GtfsAuditReport:
    """Audit GTFS stops & stop_times for broken links, backwards times, speed spikes & bus bunching."""
    findings: list[GtfsFinding] = []
    stop_map: dict[str, GtfsStop] = {}
    for st in stops:
        if not (-90.0 <= st.lat <= 90.0 and -180.0 <= st.lon <= 180.0) or (
            abs(st.lat) < 1e-6 and abs(st.lon) < 1e-6
        ):
            findings.append(
                GtfsFinding(
                    "GTFS-001", "error", st.stop_id, f"Invalid or Null-Island coordinates ({st.lat}, {st.lon})."
                )
            )
        stop_map[st.stop_id] = st

    trips_grouped: dict[str, list[GtfsStopTime]] = defaultdict(list)
    for stime in stop_times:
        trips_grouped[stime.trip_id].append(stime)

    # route_id -> list of first-stop departure seconds
    route_starts: dict[str, list[int]] = defaultdict(list)

    for trip_id, seq_items in sorted(trips_grouped.items()):
        ordered = sorted(seq_items, key=lambda x: x.stop_sequence)
        if not ordered:
            continue
        route_id = ordered[0].route_id

        prev_dep_sec: int | None = None
        prev_stop: GtfsStop | None = None
        for idx, item in enumerate(ordered):
            if item.stop_id not in stop_map:
                findings.append(
                    GtfsFinding("GTFS-002", "error", trip_id, f"Stop '{item.stop_id}' referenced in trip not found.")
                )
                continue
            try:
                arr_sec = parse_gtfs_seconds(item.arrival_time)
                dep_sec = parse_gtfs_seconds(item.departure_time)
            except ValueError as exc:
                findings.append(GtfsFinding("GTFS-003", "error", trip_id, str(exc)))
                continue

            if dep_sec < arr_sec:
                findings.append(
                    GtfsFinding(
                        "GTFS-003",
                        "error",
                        trip_id,
                        f"Departure {item.departure_time} precedes arrival {item.arrival_time} at stop {item.stop_id}.",
                    )
                )
            if idx == 0:
                route_starts[route_id].append(dep_sec)

            cur_stop = stop_map[item.stop_id]
            if prev_dep_sec is not None and prev_stop is not None:
                dt_sec = arr_sec - prev_dep_sec
                if dt_sec < 0:
                    findings.append(
                        GtfsFinding(
                            "GTFS-004",
                            "error",
                            trip_id,
                            f"Backward travel time ({dt_sec}s) from {prev_stop.stop_id} to {cur_stop.stop_id}.",
                        )
                    )
                else:
                    dist_km = haversine_km(prev_stop.lat, prev_stop.lon, cur_stop.lat, cur_stop.lon)
                    if dt_sec == 0 and dist_km > 0.25:
                        findings.append(
                            GtfsFinding(
                                "GTFS-005",
                                "error",
                                trip_id,
                                (
                                    f"Zero-second teleportation of {dist_km:.2f} km "
                                    f"between {prev_stop.stop_id} and {cur_stop.stop_id}."
                                ),
                            )
                        )
                    elif dt_sec > 0:
                        speed_kmh = dist_km / (dt_sec / 3600.0)
                        if speed_kmh > max_plausible_speed_kmh:
                            findings.append(
                                GtfsFinding(
                                    "GTFS-005",
                                    "warning",
                                    trip_id,
                                    (
                                        f"Implausible inter-stop speed {speed_kmh:.1f} km/h "
                                        f"({prev_stop.stop_id}->{cur_stop.stop_id})."
                                    ),
                                )
                            )
            prev_dep_sec = dep_sec
            prev_stop = cur_stop

    # Compute per-route headway regularity & bus-bunching index
    route_metrics: list[RouteHeadwayMetrics] = []
    for route_id, starts in sorted(route_starts.items()):
        starts_sorted = sorted(starts)
        n = len(starts_sorted)
        span_hr = (starts_sorted[-1] - starts_sorted[0]) / 3600.0 if n >= 2 else 0.0
        if n < 2:
            route_metrics.append(RouteHeadwayMetrics(route_id, n, 0.0, 0.0, 0, round(span_hr, 2)))
            continue
        headways_min = [(starts_sorted[i] - starts_sorted[i - 1]) / 60.0 for i in range(1, n)]
        mean_hw = sum(headways_min) / len(headways_min)
        if len(headways_min) >= 2 and mean_hw > 0:
            sd = math.sqrt(sum((h - mean_hw) ** 2 for h in headways_min) / (len(headways_min) - 1))
            cv = sd / mean_hw
        else:
            cv = 0.0
        bunched = sum(1 for h in headways_min if mean_hw > 0 and h < 0.5 * mean_hw)
        if cv >= 0.40 or bunched > 0:
            findings.append(
                GtfsFinding(
                    "GTFS-006",
                    "warning",
                    route_id,
                    f"Irregular headway / bunching on route '{route_id}' (CV={cv:.2f}, bunched={bunched}).",
                )
            )
        route_metrics.append(
            RouteHeadwayMetrics(
                route_id=route_id,
                trips_count=n,
                mean_headway_min=round(mean_hw, 2),
                headway_cv=round(cv, 3),
                bunched_departures=bunched,
                service_span_hours=round(span_hr, 2),
            )
        )

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    return GtfsAuditReport(
        stops_count=len(stops),
        trips_count=len(trips_grouped),
        passed=(errors == 0),
        error_count=errors,
        warning_count=warnings,
        route_metrics=tuple(route_metrics),
        findings=tuple(findings),
    )
