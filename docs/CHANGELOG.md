# Changelog

All notable changes to this project will be documented in this file.

The format follows a simplified version of Keep a Changelog.

---

## [0.1.0] - 2026-02-22

### Added
- Initial project structure
- JSON parsing from GymRats export
- Daily leaderboard generation
- Weekend and national holiday filtering (2026)
- Weekly champion calculation
- Cardio session extraction
- Weekly cardio metrics
- Progress tracking (cumulative km and best week)
- Deduplication logic for check-ins and workouts
- Export filename validation
- Execution manifest (run_manifest.json)

### Changed
- Replaced deprecated `datetime.utcnow()` with timezone-aware datetime

---

## Planned
- CLI support
- Modular refactoring
- Logging system
- Packaging improvements