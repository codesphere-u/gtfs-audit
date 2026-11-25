"""gtfs-audit — GTFS & informal paratransit validator and headway regularity analyzer."""

from gtfs_audit.validator import (
    GtfsAuditReport,
    GtfsFinding,
    GtfsStop,
    GtfsStopTime,
    RouteHeadwayMetrics,
    audit_gtfs_feed,
    haversine_km,
    parse_gtfs_seconds,
)

__version__ = "0.1.0"

__all__ = [
    "GtfsAuditReport",
    "GtfsFinding",
    "GtfsStop",
    "GtfsStopTime",
    "RouteHeadwayMetrics",
    "__version__",
    "audit_gtfs_feed",
    "haversine_km",
    "parse_gtfs_seconds",
]
