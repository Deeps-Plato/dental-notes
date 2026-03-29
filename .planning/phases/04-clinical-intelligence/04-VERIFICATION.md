---
phase: 04-clinical-intelligence
verified: 2026-03-28T00:00:00Z
status: gaps_found
score: 13/15 must-haves verified
gaps:
  - truth: "Selected appointment type flows into Whisper hotwords during live SSE transcription"
    status: failed
    reason: "The SSE route computes hotwords = TEMPLATE_HOTWORDS.get(appt_type) but the variable is never used. Transcription runs inside SessionManager._processing_loop() which calls self._whisper.transcribe(chunk) without hotwords. The hotwords computation in routes.py is dead code."
    artifacts:
      - path: "src/dental_notes/ui/routes.py"
        issue: "hotwords computed at line 295 in session_stream() but never passed to SessionManager or whisper_service.transcribe()"
      - path: "src/dental_notes/session/manager.py"
        issue: "_processing_loop() at line 267 calls self._whisper.transcribe(chunk) with no hotwords parameter; SessionManager has no mechanism to accept hotwords from the routes layer"
    missing:
      - "SessionManager needs a set_hotwords(hotwords: str | None) method (or hotwords passed to start()) so the processing loop can forward them to whisper_service.transcribe()"
      - "routes.session_start() should call session_manager.set_hotwords(...) after setting app.state.appointment_type"
      - "Alternatively, remove the dead hotwords computation from session_stream() if the decision is that hotwords are not wired during live recording (then update SUMMARY claim and requirements traceability)"
human_verification:
  - test: "Test 1: Template Selection and Re-extraction (CLI-06)"
    expected: "Review page shows appointment type dropdown with 6 options; re-extraction with a changed template produces SOAP notes with different emphasis; tab state preserved during re-extraction"
    why_human: "UI rendering, re-extraction SOAP note quality, and tab state cannot be verified programmatically"
  - test: "Test 2: Patient Summary Plain Language (REV-04)"
    expected: "Generated patient summary uses plain language (~6th grade), no CDT codes or clinical jargon, 3 distinct sections visible in editable textareas; Print Summary opens clean print layout"
    why_human: "Reading level, absence of jargon, and print layout require visual inspection"
  - test: "Test 3: 3-way Speaker Labels in Transcript (CLI-07)"
    expected: "Transcript panel shows Doctor, Patient, and Assistant labels where appropriate"
    why_human: "Requires a real recording with an assistant present; cannot verify from static files"
---

# Phase 4: Clinical Intelligence Verification Report

**Phase Goal:** The extraction pipeline produces richer, more accurate clinical notes — with procedure-specific templates, 3-way speaker attribution, expanded dental vocabulary, and a plain-language patient summary
**Verified:** 2026-03-28
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | DENTAL_INITIAL_PROMPT covers anesthetics/meds, materials/brands, pathology/findings, and anatomy/surfaces under ~224 token limit | VERIFIED | 836 chars (~209 tokens); Lidocaine, Septocaine, Marcaine, Herculite, radiolucency, CEJ, furcation all present in vocab.py |
| 2 | WhisperService.transcribe() accepts and forwards an optional hotwords parameter to faster-whisper | VERIFIED | whisper_service.py lines 63-88; hotwords kwarg forwarded conditionally; test coverage in test_whisper_service.py |
| 3 | A manual vocab file (plain text, one term per line) is loaded at startup and merged with the base initial_prompt | VERIFIED | vocab.py load_custom_vocab() + build_initial_prompt(); whisper_service.py __init__ calls build_initial_prompt(settings.custom_vocab_path) |
| 4 | classify_speaker() returns 'Assistant' for assistant-pattern text in addition to 'Doctor' and 'Patient' | VERIFIED | session/speaker.py; _ASSISTANT_PATTERNS with 4 categories; _assistant_re compiled; classify_speaker returns "Assistant" when assistant_score > doctor_score |
| 5 | When assistant score ties with doctor score, classify_speaker defaults to 'Doctor' | VERIFIED | session/speaker.py lines 88-89: `if doctor_score >= assistant_score and doctor_score >= patient_score: return "Doctor"` |
| 6 | SpeakerReattributor LLM prompt handles 3 roles (Doctor/Patient/Assistant) | VERIFIED | clinical/speaker.py SPEAKER_SYSTEM_PROMPT explicitly defines DOCTOR, PATIENT, ASSISTANT roles with descriptions; output format specifies all 3 values |
| 7 | AppointmentType enum has all 5 appointment types plus 'general' default | VERIFIED | clinical/models.py AppointmentType(str, Enum) with 6 values: GENERAL, COMPREHENSIVE_EXAM, RESTORATIVE, HYGIENE_RECALL, ENDODONTIC, ORAL_SURGERY |
| 8 | Each appointment template has a prompt overlay that composes with the base EXTRACTION_SYSTEM_PROMPT | VERIFIED | clinical/prompts.py TEMPLATE_OVERLAYS has 5 entries (all non-general types), each 260-303 chars; compose_extraction_prompt() appends overlay |
| 9 | ClinicalExtractor.extract() accepts optional template_type parameter and uses composed prompt | VERIFIED | extractor.py extract() has template_type: str | None = None; auto-detects when None, composes prompt for explicit type |
| 10 | extract_with_gpu_handoff() generates patient summary as second LLM call between SOAP extraction and Ollama unload | VERIFIED | extractor.py extract_with_gpu_handoff() calls extract() then _generate_patient_summary(transcript) before finally block unloads |
| 11 | PatientSummary model captures what-we-did, what-comes-next, and home-care sections | VERIFIED | clinical/models.py PatientSummary(BaseModel) with what_we_did, whats_next, home_care fields |
| 12 | Patient summary prompt instructs 6th-grade reading level with plain language and forbidden clinical jargon | VERIFIED | PATIENT_SUMMARY_PROMPT contains "6th-grade reading level", "Forbidden terms" list with CDT codes, Latin terms, medical abbreviations |
| 13 | Patient summary uses TRANSCRIPT as input (not SOAP note) to avoid jargon bleed | VERIFIED | extractor.py _generate_patient_summary(transcript) passes transcript text to Ollama; _generate_patient_summary is called before SOAP note is constructed; comment in code confirms this |
| 14 | SavedSession stores appointment_type and patient_summary fields | VERIFIED | session/store.py SavedSession has appointment_type: str = "general" and patient_summary: dict | None = None |
| 15 | Selected appointment type flows into Whisper hotwords during live SSE transcription | FAILED | SSE route computes hotwords but never passes it to SessionManager; transcription loop at manager.py:267 calls transcribe(chunk) without hotwords |

**Score:** 13/15 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/dental_notes/transcription/vocab.py` | Custom vocab loading, TEMPLATE_HOTWORDS mapping, base prompt management | VERIFIED | 142 lines; exports load_custom_vocab, TEMPLATE_HOTWORDS, build_initial_prompt, DENTAL_INITIAL_PROMPT |
| `src/dental_notes/transcription/whisper_service.py` | Updated DENTAL_INITIAL_PROMPT and hotwords-aware transcribe() | VERIFIED | Imports DENTAL_INITIAL_PROMPT from vocab.py; transcribe() accepts hotwords param |
| `src/dental_notes/session/speaker.py` | 3-way classify_speaker with _ASSISTANT_PATTERNS | VERIFIED | 97 lines; _ASSISTANT_PATTERNS defined; classify_speaker returns Doctor/Patient/Assistant |
| `src/dental_notes/clinical/speaker.py` | Updated SPEAKER_SYSTEM_PROMPT for 3 roles | VERIFIED | SPEAKER_SYSTEM_PROMPT describes DOCTOR, PATIENT, ASSISTANT roles |
| `tests/test_vocab.py` | Tests for custom vocab loading and merging | VERIFIED | 146 lines (>30 minimum); covers load_custom_vocab, TEMPLATE_HOTWORDS, build_initial_prompt, token limit |
| `src/dental_notes/clinical/models.py` | AppointmentType enum, PatientSummary model, updated ExtractionResult | VERIFIED | All three present; ExtractionResult.patient_summary: PatientSummary | None = None |
| `src/dental_notes/clinical/prompts.py` | TEMPLATE_OVERLAYS, compose_extraction_prompt(), PATIENT_SUMMARY_PROMPT, APPOINTMENT_TYPE_CLASSIFICATION_PROMPT | VERIFIED | All 4 exports present; TEMPLATE_OVERLAYS has 5 entries; compose_extraction_prompt returns base for None/general |
| `src/dental_notes/clinical/extractor.py` | Template-aware extract() with auto-detection, patient summary in GPU handoff | VERIFIED | _generate_patient_summary and _infer_appointment_type both present; extract() and extract_with_gpu_handoff() wired |
| `src/dental_notes/session/store.py` | SavedSession with appointment_type and patient_summary fields | VERIFIED | Both fields present with correct defaults |
| `tests/test_prompts.py` | Tests for template composition and patient summary prompt | VERIFIED | 196 lines (>40 minimum); covers compose_extraction_prompt, PATIENT_SUMMARY_PROMPT, APPOINTMENT_TYPE_CLASSIFICATION_PROMPT |
| `src/dental_notes/templates/_review_summary.html` | Patient summary tab content with editable textarea and print button | VERIFIED | 46 lines (>15 minimum); 3 textareas, save/copy/print buttons |
| `src/dental_notes/templates/_print_summary.html` | Print-optimized patient summary page | VERIFIED | 99 lines (>10 minimum); standalone HTML with @media print CSS, window.print() button |
| `src/dental_notes/ui/routes.py` | Template dropdown handling, hotwords wiring in SSE loop, patient summary routes, print view route | PARTIAL | appointment_type stored in app.state; save-summary and print-summary routes exist; session_extract passes template_type; HOTWORDS computed in SSE route but NOT forwarded to SessionManager transcription loop |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `whisper_service.py` | `vocab.py` | `from dental_notes.transcription.vocab import` | WIRED | Lines 17-20 import DENTAL_INITIAL_PROMPT, build_initial_prompt |
| `session/speaker.py` | classify_speaker return values | 3-way classification logic | WIRED | `return "Assistant"` at line 93 |
| `clinical/extractor.py` | `clinical/prompts.py` | compose_extraction_prompt(template_type) | WIRED | Lines 25-26 import compose_extraction_prompt; called in extract() at lines 58, 60 |
| `clinical/extractor.py` | `clinical/prompts.py` | _infer_appointment_type uses APPOINTMENT_TYPE_CLASSIFICATION_PROMPT | WIRED | Line 24 imports APPOINTMENT_TYPE_CLASSIFICATION_PROMPT; used in _infer_appointment_type() at line 136 |
| `clinical/extractor.py` | `clinical/models.py` | PatientSummary model validation | WIRED | Line 20 imports PatientSummary; used in _generate_patient_summary() at lines 167, 174 |
| `clinical/extractor.py` | PATIENT_SUMMARY_PROMPT | second LLM call in GPU handoff | WIRED | Line 23 imports PATIENT_SUMMARY_PROMPT; used in _generate_patient_summary() at line 167 |
| `session/store.py` | `clinical/models.py` | ExtractionResult with patient_summary | WIRED | store.py line 18 imports ExtractionResult; SavedSession.patient_summary mirrors ExtractionResult.patient_summary |
| `templates/index.html` | `ui/routes.py` | POST /session/start with appointment_type form field | NOT_WIRED | UX refactor removed pre-recording dropdown; index.html has no appointment_type field; routes.py session_start() always defaults to "general" (this is intentional per refactor) |
| `ui/routes.py` | `clinical/extractor.py` | extract_with_gpu_handoff(transcript, whisper_service, template_type) | WIRED | routes.py lines 254-256 and 425-430 pass template_type to extract_with_gpu_handoff() |
| `ui/routes.py (SSE)` | `whisper_service.py` | whisper_service.transcribe(audio, hotwords=TEMPLATE_HOTWORDS.get(appointment_type)) | NOT_WIRED | TEMPLATE_HOTWORDS.get(appt_type) computed but assigned to unused variable; SessionManager owns transcription internally; hotwords never reach the transcription loop |
| `templates/review.html` | tab switching JavaScript | tab-btn click handlers and tab-content toggle | WIRED | review.html has .tab-btn and .tab-content elements; review.js switchTab() handles click events |
| `static/review.js` | htmx:afterSwap | tab state restoration after HTMX swap | WIRED | review.js lines 541-544 listen for htmx:afterSwap and call restoreActiveTab() |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CLI-05 | 04-01 | Whisper vocabulary expanded with procedures, materials, surfaces, pathology, anatomy, findings using initial_prompt + hotwords parameter | PARTIAL | DENTAL_INITIAL_PROMPT expanded with all 4 categories (verified); hotwords parameter added to WhisperService.transcribe() (verified); TEMPLATE_HOTWORDS defined (verified); BUT hotwords not forwarded from SSE route to SessionManager transcription loop during live recording |
| CLI-06 | 04-02, 04-03 | 5 appointment-type templates with template-specific extraction prompts and note structures | SATISFIED | AppointmentType enum with 5 types + general; TEMPLATE_OVERLAYS with 5 entries; compose_extraction_prompt() wired into extract(); auto-detection via _infer_appointment_type(); review page dropdown for manual override; re-extraction with template change |
| CLI-07 | 04-01 | 3-way speaker classification (Doctor/Patient/Assistant) via extended text-based keyword classifier + LLM re-attribution with zero additional VRAM | SATISFIED | session/speaker.py classify_speaker() returns Doctor/Patient/Assistant; _ASSISTANT_PATTERNS with 4 categories; SPEAKER_SYSTEM_PROMPT describes 3 roles; SpeakerChunk.speaker accepts "Assistant" |
| REV-04 | 04-02, 04-03 | Plain-language patient summary generated at 6th-grade reading level alongside clinical SOAP note | SATISFIED | PatientSummary model with 3 sections; PATIENT_SUMMARY_PROMPT with 6th-grade instruction and forbidden terms; _generate_patient_summary() in GPU handoff; _review_summary.html with editable textareas and print button; _print_summary.html with @media print CSS |

---

## Anti-Patterns Found

No blockers or stubs detected in Phase 4 files. Anti-pattern scan of key files:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/dental_notes/ui/routes.py` | 295 | `hotwords = TEMPLATE_HOTWORDS.get(appt_type)` — dead assignment, variable never used | Warning | Hotwords not applied during live transcription despite SUMMARY claiming this feature works |

No TODO/FIXME/placeholder comments found in modified files. No empty implementations (return null/return {}). No console.log debug statements.

---

## Human Verification Required

### 1. Template Selection and Re-extraction (CLI-06)

**Test:** Open review page for a completed session. Verify appointment type dropdown shows 6 options (Auto-detect, Comprehensive Exam, Restorative, Hygiene/Recall, Endodontic, Oral Surgery). Change dropdown to "Restorative" and click Re-extract. After re-extraction, verify SOAP note contains restorative-emphasis content (anesthetic type/amount, material/shade details). Switch to Patient Summary tab — verify it is preserved. Switch back to Clinical Note tab.
**Expected:** Template dropdown functional, SOAP note reflects restorative template emphasis, tab state preserved across re-extraction.
**Why human:** SOAP note quality and template emphasis require semantic inspection; tab state requires UI interaction.

### 2. Patient Summary Plain Language (REV-04)

**Test:** Open review page for a session with an extracted note. Click "Patient Summary" tab. Verify 3 sections are visible (What We Did Today, What Comes Next, Home Care Instructions). Read the content for plain language (no CDT codes, no Latin dental terms, no abbreviations). Edit one section and click "Save Summary". Click "Print Summary" and verify print dialog opens with clean layout.
**Expected:** Plain language summary in 3 editable sections; no clinical jargon; print layout shows only summary content with @media print CSS hiding navigation.
**Why human:** Reading level assessment, jargon detection, and print layout require visual inspection.

### 3. 3-Way Speaker Labels in Transcript (CLI-07)

**Test:** Record a session where an assistant is present (or manually add "Assistant: suction please" to a transcript and re-extract). On the review page, verify transcript panel shows "Assistant:" label alongside "Doctor:" and "Patient:" labels.
**Expected:** Three distinct speaker labels visible in transcript display.
**Why human:** Requires real recording or manual transcript editing; visual verification needed.

---

## Gaps Summary

**One gap found: Hotwords not wired to live transcription (CLI-05 partial).**

The SSE route in `routes.py` computes `hotwords = TEMPLATE_HOTWORDS.get(appt_type)` at line 295 but the variable is assigned and then never used. The actual transcription occurs inside `SessionManager._processing_loop()` at `manager.py:267`, which calls `self._whisper.transcribe(chunk)` with no `hotwords` argument. The session manager has no mechanism to receive hotwords from the routes layer.

This means the hotwords boost defined in `TEMPLATE_HOTWORDS` for appointment-specific terms (e.g., "Lidocaine Septocaine Marcaine articaine" for restorative, "apex locator gutta-percha working length" for endodontic) is never applied during live recording regardless of which appointment type is detected or selected.

**Impact assessment:**
- TEMPLATE_HOTWORDS is defined and substantive (6 entries, each with 10-20 relevant terms)
- WhisperService.transcribe() correctly accepts and forwards the hotwords parameter
- The gap is in the routing layer: hotwords reaches the SSE handler but cannot reach the SessionManager's background thread
- REQUIREMENTS.md marks CLI-05 as "Complete" — this is overstated; the hotwords infrastructure exists but is not activated during live recording
- The 363 tests all pass because no test verifies that the SSE route's `hotwords` variable is actually passed to the session manager

**Root cause:** The UX refactor (Plan 03 deviation) moved template selection to the review page and made auto-detect the primary mechanism. This architectural change made the pre-recording hotwords path partially obsolete, but the dead code was not cleaned up and the claim in the module docstring ("session_start -> app.state.appointment_type -> SSE hotwords -> session_stop") is misleading.

**Fix options:**
1. Wire hotwords: Add `set_hotwords(hotwords: str | None)` to SessionManager; call it from session_start; use it in _processing_loop. This preserves the live accuracy boost with the general hotwords set.
2. Accept limitation: Remove the dead hotwords computation from session_stream(), update CLI-05 description to note that hotwords are defined but not applied during live recording (only at extraction time via TEMPLATE_HOTWORDS in vocab.py). The vocabulary boost still applies via DENTAL_INITIAL_PROMPT.

---

*Verified: 2026-03-28*
*Verifier: Claude (gsd-verifier)*
