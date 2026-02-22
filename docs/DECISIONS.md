# Architectural Decisions

## 1. Data Source Strategy

The system processes weekly JSON exports from GymRats Pro.

Instead of relying on a single export file, the system:
- Reads all JSON files inside the `exports/` directory
- Merges them
- Deduplicates check-ins and workouts

This ensures incremental weekly exports do not create duplicated records.

---

## 2. Timezone Handling

GymRats exports timestamps in UTC (`Z` format).

Decision:
- Convert all timestamps to `America/Sao_Paulo` timezone
- All ranking logic is based on São Paulo local date

Reason:
Using UTC directly could shift workouts to the wrong day when converting to local time.

---

## 3. Valid Days Rule (Business Logic)

Due to fairness rules within the group:

- Weekends (Saturday and Sunday) are ignored
- Brazilian national holidays for 2026 are ignored

Only confirmed national holidays are considered (excluding optional holidays).

This rule is applied BEFORE aggregating daily scores.

---

## 4. Leaderboard Aggregation

Daily leaderboard:
- Aggregate points per user per valid day
- Rank by descending points
- Detect ties (multiple rank=1 entries)

Weekly champion:
- Sum daily valid points per week
- Week starts on Monday
- Detect weekly ties

---

## 5. Cardio Metrics

Cardio activities include:
- running
- treadmill
- mixed_cardio
- walking

Although the export field is named `distance_miles`,
values appear formatted for Brazilian context (e.g., "2,6"),
so they are interpreted as kilometers.

Future improvement:
Add unit validation if needed.

---

## 6. Deduplication Strategy

Because weekly exports may overlap:

Cardio:
- Primary key: `workout_id`
- Fallback: composite key (date + start_time + activity + distance + duration)

Check-ins:
- Composite key: account_id + occurred_at + points

This prevents double counting when multiple exports are processed.

---

## 7. Execution Manifest

Each run generates `run_manifest.json` containing:
- UTC timestamp (timezone-aware)
- Number of processed files
- Processed file names
- Output record counts

This ensures traceability and basic pipeline observability.

---

## 8. Future Improvements

- CLI parametrization (year, user, export directory)
- Logging instead of print
- Modular architecture separation
- Unit tests
- Dockerization