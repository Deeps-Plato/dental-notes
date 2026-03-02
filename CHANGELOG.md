# Changelog

All notable changes to dental-notes will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial project scaffold: backend FastAPI skeleton and Flutter app structure
- `GET /health`, `POST /transcribe`, `POST /generate-note` backend routes
- SQLCipher-encrypted local storage via `drift` ORM
- SOAP note generation via Claude `claude-sonnet-4-6`
- Periodontal chart voice entry with AAP Stage/Grade classification
- 32-tooth odontogram with CDT code suggestions
- PDF export (SOAP + perio table + odontogram + medications)
- Biometric app lock with 5-minute auto-lock
