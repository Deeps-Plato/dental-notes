# Phase 3: Review and Export - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

After a recording session ends, the dentist reviews the full transcript alongside an AI-generated clinical note, edits both freely, copies the finalized note for Dentrix, and cleans up ephemeral data. Sessions can be saved for later completion — the dentist may record multiple patients in a row and batch note-writing at end of day. All processing stays local.

Phase 2 delivers ExtractionResult (SOAP note + CDT codes + clinical_discussion + speaker chunks + summary). Phase 3 builds the review/edit/export UI on top of that.

</domain>

<decisions>
## Implementation Decisions

### Extraction trigger
- Auto-extract SOAP note when session is stopped (no extra button click)
- Show loading state during GPU handoff (Whisper unload -> LLM inference)
- "Regenerate" button in review screen to re-run extraction if needed
- If dentist edits the transcript, show banner: "Transcript changed — Regenerate note?" (dentist chooses)

### Review layout
- 50/50 side-by-side split: transcript on left, clinical note on right
- Both panels scroll independently
- No transcript highlighting or color-coding — plain text with speaker labels
- Clinical Discussion appears inside the note panel as a section after CDT codes

### Note structure (richer than textbook SOAP)
- **Subjective**: Narrative + bullet point hybrid (chief complaint, symptoms, history)
- **Objective**: Bullet-heavy with some narrative (findings, tooth numbers, surfaces, probing depths)
- **Assessment**: Clear-cut (diagnoses with tooth numbers)
- **Plan**: Clear-cut with narrative for justification and contingency plans
- **CDT Codes**: Listed after Plan
- **Clinical Discussion**: Bullet-point summary of reasoning discussed with patient (diagnosis explanation, analogies, risks/benefits, treatment rationale)
- **Prescribed Medications**: Always at bottom of note — auto-extracted from transcript, dentist can correct and add more
- LLM auto-detects exam-only vs exam+procedure from transcript and adjusts format:
  - Exam+procedure notes include: Tx plan + consent notation, procedure steps/materials in Objective, future plan at end
- LLM auto-detects VA patients from transcript context (VA is mentioned in conversation) and generates per-tooth narrative section after the main note (findings + indicated procedures per tooth)

### Editing
- Everything is fully editable — SOAP note AND transcript are editable text areas
- Type, dictate, cut/copy/paste, add, delete — no restrictions, no read-only sections
- CDT codes fully editable — add, remove, modify
- Clinical Discussion bullets fully editable
- Dictation (mic-to-text) available on any editable field at any stage using the Whisper pipeline for dental term accuracy

### Copy & export
- "Copy All" button copies the entire formatted note to clipboard (one-click, REV-03)
- Per-section copy icons for granular copying when dentist only needs part of the note
- Clipboard format: plain text with section headers (Subjective, Objective, Assessment, Plan, CDT Codes, Clinical Discussion, Medications, VA Narrative if applicable)

### Session management
- Sessions are saveable — dentist can record multiple patients, save sessions, come back later
- Multiple saved sessions visible in a list with: timestamp + first line of transcript preview + status badge (Recorded / Extracted / Reviewed)
- Dentist picks which session to review/complete from the list
- Supports batch note-writing workflow (record 5 patients in the morning, write notes at lunch)

### Finalization & cleanup
- "Finalize & Clear" button explicitly deletes transcript after dentist is done (AUD-02)
- Not auto-delete on copy — two-step: copy first, then confirm finalization
- After finalization: confirmation message + clear path to "New Session" or return to session list

### Patient summary (REV-04)
- Deferred — skip for v1, focus on dentist workflow

### Claude's Discretion
- Loading/progress UI during extraction
- Session list page layout and navigation
- Exact styling and CSS for the review screen
- How dictation mic button is presented on editable fields
- Session file format for saving/resuming incomplete notes
- Error handling for Ollama unavailable during extraction

</decisions>

<specifics>
## Specific Ideas

- The dentist often goes room-to-room without stopping: record patient A, save, record patient B, save, then come back and do notes for both. The session list is the home screen between appointments.
- VA patients always discuss VA in conversation — the LLM can detect this without a toggle. Per-tooth narrative is a separate section written after the full note is formulated.
- Procedure notes somewhat repeat: exam findings appear in Objective, then procedure steps/materials appear in a second Objective-like section. Tx plan and consent are noted before procedure details.
- "Finalize" is a conscious act — the dentist confirms they're done before data is deleted. No accidental data loss.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ClinicalExtractor.extract()`: Produces ExtractionResult with SOAP note, CDT codes, clinical_discussion, speaker chunks, clinical summary
- `ClinicalExtractor.extract_with_gpu_handoff()`: Manages Whisper unload -> LLM -> LLM unload -> Whisper reload sequence
- `SpeakerReattributor.reattribute()`: Corrects speaker labels using LLM context
- `OllamaService`: Ollama client with structured output, health checks, model unloading
- `SessionManager`: Tracks session state (IDLE/RECORDING/PAUSED), stores chunks as `list[tuple[str, str]]`
- HTMX + SSE patterns from Phase 1 (OOB swap, SSE streaming, Jinja2 templates)
- `static/style.css`: Existing stylesheet for the recording UI

### Established Patterns
- FastAPI + HTMX web UI with Jinja2 templates and SSE streaming
- Routes return HTML partials for HTMX swaps (no JSON API for UI)
- Session state machine: IDLE -> RECORDING -> PAUSED -> RECORDING -> IDLE
- GPU memory management via model unload/reload sequences
- Transcript stored as `list[tuple[str, str]]` (speaker, text) in SessionManager
- Transcript files saved to `transcripts/session_YYYYMMDD_HHMMSS.txt`

### Integration Points
- After session stop: trigger ClinicalExtractor.extract_with_gpu_handoff()
- Review screen replaces/extends the current transcript display
- Session list requires persistence beyond in-memory SessionManager (file-based or SQLite)
- Clipboard copy via JavaScript `navigator.clipboard.writeText()`
- Dictation fields reuse WhisperService for mic-to-text input

</code_context>

<deferred>
## Deferred Ideas

- REV-04 (patient summary as patient-facing handout) — future version
- Streaming LLM output (show SOAP note building in real-time) — v2 enhancement
- Appointment-type templates (exam, restorative, hygiene, endo, extraction) — v2 requirement ENH-01

</deferred>

---

*Phase: 03-review-and-export*
*Context gathered: 2026-03-10*
