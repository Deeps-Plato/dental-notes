# Phase 2: Clinical Extraction - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning
**Source:** User conversation + PROJECT.md decisions + Phase 1 testing feedback

<domain>
## Phase Boundary

This phase adds the clinical intelligence layer: a local LLM (Ollama with Qwen3 8B) processes the accumulated transcript from Phase 1, filters out social conversation, structures clinical content into a dental SOAP note with CDT codes, and re-attributes speaker labels using conversational context. All processing stays local — no patient data leaves the machine.

Phase 1 delivers a plain-text transcript with keyword-based speaker labels. Phase 2 takes that transcript and produces structured clinical output. Phase 3 will build the review/edit UI on top of Phase 2's output.

</domain>

<decisions>
## Implementation Decisions

### LLM Stack (Locked — from PROJECT.md)
- Ollama for local LLM hosting — no cloud APIs, no patient data transmitted
- Qwen3 8B as the target model — fits in 8GB VRAM alongside or sequentially with Whisper
- Sequential GPU loading: Whisper and LLM cannot coexist in VRAM on GTX 1050 (4GB) — must unload Whisper before loading LLM, or use CPU fallback
- GTX 1070 Ti (8GB) is the common hardware — may support both models simultaneously

### Clinical Processing (Locked)
- Input: plain-text transcript with keyword-based speaker labels from Phase 1
- Output: structured SOAP note (Subjective, Objective, Assessment, Plan) + CDT codes
- Chitchat filtering: LLM identifies and removes social conversation, keeping only clinically relevant content
- CDT code suggestions: extracted from the Assessment and Plan sections of the SOAP note

### Speaker Re-Attribution (Locked — from user testing feedback)
- Phase 1's keyword classifier misidentifies doctor speech when doctor pauses mid-thought
- LLM must re-attribute speaker labels using conversational context:
  - Who leads, instructs, directs → Doctor
  - Who responds, reports symptoms, asks personal questions → Patient
  - Continuity across pauses (same speaker unless clear turn-taking signal)
- The LLM pass produces final speaker labels; keyword labels are a real-time preview only

### Privacy (Locked)
- All LLM inference runs locally via Ollama — PRV-01 still applies
- No Ollama cloud features, no model telemetry
- Transcript data stays in memory during processing, not written to additional files

### TDD Methodology (Locked)
- Test file before implementation file
- Integration test mandatory: prove transcript → LLM → SOAP note pipeline works end-to-end
- Human verification checkpoint: user must confirm SOAP note quality from a real dental transcript
- No mocking away the LLM — use real Ollama in integration tests (or a realistic fake that validates prompt/response structure)

### Claude's Discretion
- Prompt engineering for the SOAP note extraction (system prompt, few-shot examples, output format)
- How to handle the Whisper→LLM GPU handoff (sequential loading vs CPU fallback)
- Ollama client library choice (ollama-python, httpx to Ollama REST API, or subprocess)
- Whether to process the full transcript at once or in sections
- CDT code lookup strategy (embedded list vs prompted knowledge)
- Error handling when Ollama is not running or model not pulled

</decisions>

<specifics>
## Specific Details

### Existing Infrastructure
- Phase 1 produces transcript files in `transcripts/session_YYYYMMDD_HHMMSS.txt`
- SessionManager stores chunks as `list[tuple[str, str]]` (speaker, text)
- WhisperService loads/unloads models and tracks GPU state
- FastAPI app at localhost:8000 with HTMX/SSE UI

### Dental SOAP Note Structure
- **Subjective**: Chief complaint, patient-reported symptoms, pain description, onset/duration
- **Objective**: Clinical findings (tooth numbers, surfaces, conditions), radiographic findings, vitals if relevant
- **Assessment**: Diagnosis with tooth numbers, classification (e.g., "caries D2 #14"), staging
- **Plan**: Procedures planned (with CDT codes), materials, next visit, patient instructions

### CDT Code Examples
- D0120: Periodic oral evaluation
- D0220: Periapical radiograph
- D2391-D2394: Posterior composite restorations (1-4+ surfaces)
- D2740: Crown — porcelain/ceramic
- D3330: Root canal — molar
- D4341: Periodontal scaling and root planing (per quadrant)

### Target Hardware
- Minimum: GTX 1050 (4GB VRAM) — may need CPU-only LLM or very small model
- Common: GTX 1070 Ti (8GB VRAM) — should handle Qwen3 8B quantized
- Whisper (small, int8) uses ~1-2GB VRAM during transcription

</specifics>

<deferred>
## Deferred Ideas

- Multi-model comparison (try different local LLMs and compare quality) — v2+ optimization
- Streaming LLM output (show SOAP note building in real-time) — Phase 3 UI concern
- Appointment-type templates (exam vs restorative vs hygiene) — v2 requirement ENH-01
- Speaker diarization from audio features — v2 requirement ENH-02

</deferred>

---

*Phase: 02-clinical-extraction*
*Context gathered: 2026-03-08 via user conversation and Phase 1 testing feedback*
