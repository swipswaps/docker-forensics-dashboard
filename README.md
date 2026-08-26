# Forensic Investigation Archive - 2026-08-26

## Context
This directory contains forensic data captured from a Fedora 43 system experiencing performance issues with multiple Docker backends running.

## Files
- forensic_investigation.py - The investigation tool
- forensic_logs.db - SQLite database with all captured data
- snapshot_*.json - Three snapshots taken 2 seconds apart
- forensic_report.json - Generated summary report

## Findings
The investigation captured:
- 3 system snapshots
- Process lists with CPU/memory usage
- Docker container status and resource usage
- System load averages and memory metrics

## Security Note
This data contains sensitive system information and should be handled securely.

## How to View Data
sqlite3 forensic_logs.db "SELECT * FROM process_snapshots LIMIT 10;"
sqlite3 forensic_logs.db "SELECT * FROM docker_containers;"
cat forensic_report.json | python3 -m json.tool
