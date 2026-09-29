# POLARIS field app (Flutter, offline-first) — Phase 3.1

Every local write becomes a `SyncEvent`
`{ event_id, device_id, user_id, event_type, entity_id, timestamp, payload, sync_status }`
stored in SQLite (`sync_events`), `sync_status: PENDING|UPLOADING|ACKNOWLEDGED`.

Screens: Scan (QR → `CARGO_SCANNED`, shows "Saved locally — SYNC: PENDING"),
Queue (PENDING list + Sync now), Issue (`INVENTORY_ISSUE`), Check-in
(`FIELD_CHECK_IN`), Team (personnel cache placeholder). AppBar has an
airplane-mode toggle for the demo: ON = everything stays PENDING.

Backend upload (`POST /api/v1/sync/events` batch) lands in Phase 3.2 —
`SyncApi.uploadBatch` already targets that contract.

## Run (needs Flutter SDK — not installed on this machine)

```powershell
flutter pub get
flutter analyze
flutter run  # airplane-toggle: Scan → Queue shows PENDING → Sync now → ACKNOWLEDGED
```
