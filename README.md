# Docker Forensics Investigation Tool

## Purpose
A Python-based forensic investigation tool for capturing system processes, Docker containers, and system metrics on Linux systems.

## Features
- Captures 3 snapshots (2 seconds apart) of system state
- Stores data in SQLite database and JSON format
- Monitors Docker containers with resource usage
- Generates summary report with high-resource processes
- Secure data separation - no data stored in repository

## Installation
git clone https://github.com/swipswaps/docker-forensics-dashboard.git
cd docker-forensics-dashboard

## Usage
python3 forensic_investigation.py /path/to/data/directory

## Environment Variable
export FORENSIC_DATA_DIR=/custom/data/path
python3 forensic_investigation.py $FORENSIC_DATA_DIR

## Output Files
- forensic_logs.db - SQLite database with all captured data
- snapshot_*.json - Three snapshots taken 2 seconds apart
- forensic_report.json - Generated summary report

## Security
All forensic data is stored in the user-specified directory and is never committed to this repository. Use the FORENSIC_DATA_DIR environment variable for secure storage locations.

## License
MIT License
