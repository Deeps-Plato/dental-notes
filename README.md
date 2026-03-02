# dental-notes

Chairside AI-assisted dental note-taking. Captures audio, transcribes via self-hosted Whisper,
and generates structured SOAP notes, periodontal charts, and odontogram data using Claude.

```
┌─────────────────────────────────────────────────────────────────┐
│                      dental-notes architecture                  │
│                                                                 │
│  iPhone / iPad / Android                                        │
│  ┌──────────────────────┐                                       │
│  │   Flutter App        │──── HTTPS (ngrok/Tailscale) ────┐    │
│  │  • record audio      │                                  ▼    │
│  │  • display SOAP note │          WSL2 / Mac              │    │
│  │  • perio chart       │   ┌──────────────────────────┐   │    │
│  │  • odontogram        │   │  FastAPI backend          │   │    │
│  │  • SQLCipher DB      │   │  • POST /transcribe       │   │    │
│  └──────────────────────┘   │    faster-whisper (CUDA)  │   │    │
│                             │  • POST /generate-note    │   │    │
│                             │    Claude sonnet-4-6      │   │    │
│                             │  audio deleted immediately │   │    │
│                             └──────────────────────────┘   │    │
│                                                              │    │
│  PHI stays on device (SQLCipher AES-256)                    │    │
│  Backend is stateless — no patient data persisted           │    │
└─────────────────────────────────────────────────────────────────┘
```

## Requirements

- **Backend:** Python 3.12+, NVIDIA GPU + CUDA (for faster-whisper), Anthropic API key
- **App:** Flutter 3.19+, Dart 3.3+
- **Dev exposure:** ngrok or Tailscale (to reach backend from iOS device)

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env   # fill in DENTAL_API_KEY and ANTHROPIC_API_KEY
uvicorn dental_notes_backend.main:app --host 0.0.0.0 --port 8765 --reload
```

Expose to device (dev):
```bash
ngrok http 8765 --scheme https
```

### Flutter App

```bash
cd app
flutter pub get
flutter run -d <device-id>
```

Set the backend URL in the app's Settings screen (stored in secure storage, never in code).

## Configuration

All backend config lives in `.env` (see `.env.example`). The Flutter app stores the backend URL
and API key in the platform keychain via `flutter_secure_storage`.

## HIPAA Notice

> **This software is provided for development and evaluation purposes only.**
> Before using with real patient data you must:
> 1. Execute a Business Associate Agreement (BAA) with Anthropic at console.anthropic.com
> 2. Complete a full HIPAA security risk assessment for your deployment environment
> 3. Implement appropriate access controls, workforce training, and incident response procedures
>
> The authors make no warranties regarding HIPAA compliance for any specific deployment.

## Architecture

- **Backend:** Stateless FastAPI — audio is transcribed and immediately deleted; no PHI persisted
- **App storage:** SQLCipher AES-256 encrypted SQLite via `drift` ORM; key in platform keychain
- **Auth:** `X-API-Key` header on all backend requests; biometric/PIN app lock with 5-min timeout
- **Transit:** HTTPS enforced; Tailscale or ngrok for dev; reject plain HTTP in Dio

## Contributing

```bash
# Backend
ruff check backend/src/ backend/tests/
mypy backend/src/
pytest backend/tests/

# Flutter
flutter analyze app/
flutter test app/
```
