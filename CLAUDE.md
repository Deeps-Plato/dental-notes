# CLAUDE.md — dental-notes

> Project-specific instructions for Claude Code and Codex sessions.

## What This Project Is

HIPAA-aligned dental note-taking app. Captures chairside audio → self-hosted Whisper transcription → Claude-generated structured SOAP notes, periodontal charts, and odontogram data. All PHI stays on-device (SQLCipher AES-256). Backend is stateless — audio transcribed and immediately deleted.

**Status:** All 7 build phases complete. 128 tests passing (115 Flutter + 13 backend).

---

## Project Layout

```
~/claude/dental-notes/
├── backend/                    # Python 3.12 FastAPI (stateless, no PHI)
│   ├── pyproject.toml
│   ├── src/dental_notes_backend/
│   │   ├── main.py             # App factory, lifespan, JSON logging, rate limiter
│   │   ├── config.py           # pydantic-settings (.env → typed Settings)
│   │   ├── auth.py             # X-API-Key middleware
│   │   ├── routes/             # health.py, transcribe.py, notes.py
│   │   ├── services/           # whisper_service.py, claude_service.py
│   │   ├── models/             # api_models.py (Pydantic)
│   │   └── prompts/            # soap_note.py, perio_parse.py, medication_extract.py
│   └── tests/
│
├── app/                        # Flutter (iOS, Android, Windows, macOS)
│   ├── pubspec.yaml
│   ├── lib/
│   │   ├── main.dart
│   │   ├── app.dart            # MaterialApp + ProviderScope
│   │   ├── core/               # constants, theme, router, errors
│   │   ├── data/
│   │   │   ├── database/       # tables.dart (7 drift tables), app_database.dart (schema v2)
│   │   │   ├── models/         # freezed: patient, visit, soap_note, perio_chart, odontogram
│   │   │   └── repositories/   # patient, visit, soap_note, perio, odontogram (all with audit)
│   │   ├── domain/             # perio_logic, odontogram_logic, pdf_generator
│   │   ├── network/            # api_client, transcribe_api, notes_api
│   │   ├── features/           # auth, patients, visit, soap_note, perio_chart,
│   │   │                       # odontogram, medications, pdf_export, settings
│   │   └── shared/             # widgets (audio_recorder_button, loading_overlay),
│   │                           # providers (database_provider)
│   └── test/                   # 15 test files, 115 tests
│
├── STATE.md                    # Comprehensive project state (architecture, phases, coverage)
├── CHANGELOG.md
├── SECURITY.md
└── .gitignore                  # PHI patterns, .g.dart, .freezed.dart, .env, *.db
```

---

## Dev Commands

### Backend

```bash
cd ~/claude/dental-notes/backend
source .venv/bin/activate

uvicorn dental_notes_backend.main:app --port 8765 --reload    # run server
pytest tests/                                                   # 13 tests
ruff check src/ tests/                                          # lint
mypy src/ --ignore-missing-imports                              # type check
```

Env vars needed in `.env`: `DENTAL_API_KEY`, `ANTHROPIC_API_KEY`

### Flutter App

```bash
cd ~/claude/dental-notes/app

~/flutter/bin/flutter test                                              # 115 tests
~/flutter/bin/flutter analyze                                           # lint
~/flutter/bin/dart run build_runner build --delete-conflicting-outputs   # codegen
~/flutter/bin/flutter run -d <device-id>                                # run
```

**Important:** Flutter is at `~/flutter/bin/flutter`, not on PATH.

---

## Critical Conventions

### Code Generation

- `.g.dart` and `.freezed.dart` files are **gitignored** — they must be regenerated after checkout
- Run `dart run build_runner build --delete-conflicting-outputs` before building
- Never hand-edit `.g.dart` or `.freezed.dart` files

### Riverpod 2.x (NOT 3.0)

- Uses generated `XxxRef` types (e.g., `PatientListRef`, `NotesApiRef`)
- Do **not** replace these with bare `Ref` — that's a Riverpod 3.0 API
- Provider overrides in tests:
  - Sync repos: `.overrideWithValue(repo)`
  - Async APIs: `.overrideWith((ref) async => fakeApi)`
- 19 info-level deprecation warnings exist — acceptable until Riverpod 3.0 migration

### API JSON Keys — snake_case from Python, camelCase in Dart

- Python backend sends `snake_case` keys (`drug_name`, `change_type`, `clinical_findings`)
- Dart freezed models use `camelCase` (`drugName`, `changeType`, `clinicalFindings`)
- `notes_api.dart` manually maps between the two using `_parseSoapResponse`, `_parseMedChange`
- Do **not** use `MedicationChange.fromJson` for API responses — it expects camelCase
- If adding new API response fields, map them manually in `notes_api.dart`

### Testing Patterns

- **In-memory DB:** `AppDatabase(NativeDatabase.memory())` — no SQLCipher in tests
- **Fakes over Mocks:** Use hand-written `Fake` classes, not mockito `Mock` — avoids null-safety issues with `any` returning null for non-nullable params
- **drift import conflict:** When importing `package:drift/drift.dart` in tests, use `hide isNull, isNotNull` to avoid conflict with matcher package
- **Trailing commas:** Analysis enforces `require_trailing_commas` — always add trailing commas to argument lists

### Database

- Schema version: **2** (v1 → v2 added Odontograms table)
- 7 tables: Patients, Visits, SoapNotes, PerioCharts, PerioReadings, Odontograms, AuditLogs
- All repository mutations write to AuditLogs (action, entityType, entityId, timestamp)
- Production DB encrypted with SQLCipher; key stored in platform keychain via `flutter_secure_storage`

### HIPAA Rules

- **Never** persist patient names, DOBs, or any PHI in backend logs or responses
- **Never** commit `.env`, `*.db`, `*.key`, or files under `patient_data/`, `recordings/`, `exports/`
- Backend audio files: write to temp → transcribe → **delete immediately** → return transcript
- PDF filenames: `visit_{YYYYMMDD}.pdf` — no patient name in filename
- Audit log every DB mutation — no exceptions

---

## Architecture Details

### Backend API (3 endpoints)

| Endpoint | Purpose | Auth | Rate Limit |
|----------|---------|------|-----------|
| `GET /health` | Whisper model status | X-API-Key | none |
| `POST /transcribe` | Audio file → transcript (multipart) | X-API-Key | 10/min |
| `POST /generate-note` | Transcript → structured note (JSON) | X-API-Key | 10/min |

`/generate-note` accepts `note_type`: `soap`, `perio_parse`, or `medication_extract`

### Database Tables

| Table | Key Relationships |
|-------|------------------|
| Patients | standalone |
| Visits | → Patients (FK) |
| SoapNotes | → Visits (FK), one per visit (upsert) |
| PerioCharts | → Visits (FK), one per visit (ensureChart) |
| PerioReadings | → PerioCharts (FK), many per chart |
| Odontograms | → Visits (FK), one per visit, teeth stored as JSON |
| AuditLogs | standalone (action, entityType, entityId) |

### Domain Logic

- **PerioLogic** (`domain/perio_logic.dart`): AAP 2017 Stage I–IV from max probing depth + tooth loss; Grade A–C from BOP% + risk factors (diabetic, smoker)
- **OdontogramLogic** (`domain/odontogram_logic.dart`): CDT code suggestions per surface condition, Universal tooth numbering (1–32)
- **PdfGenerator** (`domain/pdf_generator.dart`): Multi-page PDF with SOAP note, perio summary, medications

### Navigation (go_router)

```
/patients → /patients/:patientId → /patients/:patientId/visit/:visitId
                                      ├── .../soap
                                      ├── .../perio
                                      ├── .../odontogram
                                      ├── .../medications
                                      └── .../pdf
/settings
```

---

## Test Coverage Summary

| Layer | Files | Tests |
|-------|-------|-------|
| Repositories | 5 | 50 |
| Notifiers | 4 | 30 |
| Network APIs | 2 | 13 |
| Domain logic | 3 | 23 |
| Widget | 1 | 1 (placeholder) |
| **Flutter total** | **15** | **115** |
| **Backend total** | **4** | **13** |

All business logic is covered. UI screens and widgets are not unit-tested.

---

## Known Issues

| Issue | Notes |
|-------|-------|
| Riverpod 2.x deprecation warnings | 19 info-level; will resolve with Riverpod 3.0 migration |
| No CI pipeline | `.github/workflows/ci.yml` not yet created |
| No widget/integration tests | Business logic tested; screens untested |
| Anthropic BAA not signed | Required before any real patient data |

---

## Dental Domain Reference

- **Tooth numbering:** Universal system, 1–32 (1 = upper right 3rd molar, clockwise)
- **Perio probing:** 6 points per tooth (buccal: MB/B/DB; lingual: ML/L/DL) = 192 readings for full mouth
- **Depth color coding:** 1–3mm green, 4–5mm yellow, ≥6mm red; BOP = red dot
- **AAP Staging:** I (≤4mm), II (≤5mm), III (≥6mm), IV (≥6mm + ≥5 teeth lost)
- **CDT codes:** Dental procedure codes (e.g., D0120 = periodic exam, D3330 = root canal molar, D2391 = posterior composite)
- **Voice perio pattern:** "Tooth fourteen buccal three-two-four BOP" → parsed to PerioReading
- **SOAP:** Subjective, Objective (clinical + radiographic + vitals), Assessment, Plan (today + next visit + patient instructions + CDT codes)
