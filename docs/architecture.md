# Architecture — `gtfs-audit`

- `gtfs_audit.validator`: GTFS >24h `HH:MM:SS` parser, WGS84 stop coordinate & Null-Island validator (`GTFS-001`), referential integrity (`GTFS-002`), dwell & backward travel-time checks (`GTFS-003`/`004`), Haversine inter-stop speed/teleportation detector (`GTFS-005`), and route headway regularity CV + bus-bunching index (`GTFS-006`).
- `gtfs_audit.cli`: Kampala transit corridor GTFS audit demo CLI.
