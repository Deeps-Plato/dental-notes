# Phase 4: Clinical Intelligence - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Enhance the extraction pipeline to produce richer, more accurate clinical notes. Four capabilities: (1) expanded Whisper dental vocabulary via initial_prompt + hotwords, (2) 5 appointment-type templates with template-specific extraction prompts, (3) 3-way speaker classification (Doctor/Patient/Assistant) via text-based keywords + LLM re-attribution, and (4) plain-language patient summary for patient handouts. All processing stays local. No new GPU-consuming models — zero additional VRAM.

Phase 3 delivered a working review/edit/export UI with 249 tests. Phase 4 enhances the clinical intelligence feeding into that UI. Phase 5 will add batch workflow and error recovery on top.

</domain>

<decisions>
## Implementation Decisions

### Vocabulary Strategy (CLI-05)
- Global expansion of `DENTAL_INITIAL_PROMPT` covering all 4 term categories: anesthetics/meds (Lidocaine, Septocaine, Marcaine, epi concentrations), materials/brands (Herculite, Estelite, Paracore, Luxatemp, Fuji, IRM, Dycal), pathology/findings (radiolucency, periapical, dehiscence, fenestration, caries classification), anatomy/surfaces (mandibular canal, mental foramen, CEJ, furcation, lingual/buccal/mesial/distal)
- Use faster-whisper `hotwords` parameter for procedure-specific term boosting per appointment template
- Vocabulary is baked-in (one comprehensive set for all offices), not per-office configurable
- Learn-as-you-go strategy: manual vocab file (plain text, loaded at startup, merged with base prompt) for v2. Auto-detection from review screen corrections deferred to v3.
- Must respect ~224 token limit for initial_prompt — prioritize most-misrecognized terms

### Template Selection UX (CLI-06)
- Dropdown + auto-detect hybrid: show appointment type dropdown before recording, default to "General"
- If no template selected, LLM auto-detects appointment type from transcript during extraction
- 5 templates: comprehensive exam, restorative, hygiene/recall, endodontic, oral surgery
- Same SOAP structure (S/O/A/P) for all templates — LLM emphasizes different details per template (e.g., restorative emphasizes materials/shade/anesthetic, hygiene emphasizes probing/BOP/home care)
- Template changeable at review time — selecting a different template triggers re-extraction with the new template's prompt
- Template selection flows into: (a) Whisper hotwords during recording, (b) extraction system prompt, (c) review page display

### 3-Way Speaker Classification (CLI-07)
- Extend existing text-based keyword classifier to recognize 3 roles: Doctor, Patient, Assistant
- Assistant keyword patterns across all 4 categories:
  - Instrument/supply calls: "suction", "two-by-two", "explorer", "cotton roll", "bite block", "matrix band", "wedge"
  - Patient comfort: "you're doing great", "almost done", "rinse and spit", "are you okay?"
  - Procedural assists: "isolation complete", "impression set", "light cure", "mixing"
  - Charting/admin: "noted", "got it", "which tooth?", "what shade?"
- Moderate overlap between assistant and doctor speech is expected — best effort is acceptable, not perfect accuracy
- LLM SpeakerReattributor enhanced with 3-role prompt (Doctor/Patient/Assistant)
- Room composition varies: exams typically 2 people (doc + patient), procedures typically 3+ (doc + assistant + patient), sometimes hygienist instead of assistant
- If classifier is uncertain, default behavior: mark as doctor speech (safer for clinical note content)
- No audio-based diarization — text-based + LLM only, zero VRAM cost

### Patient Summary (REV-04)
- Content includes: what was done today (plain-language procedures and findings), what comes next (upcoming appointments, follow-up), home care instructions (post-op care, medications, dietary restrictions)
- Does NOT include: insurance/cost notes, CDT codes, clinical jargon
- Reading level: approximately 6th grade — plain language, no medical abbreviations
- Delivery: print-ready HTML page the dentist can print directly from the browser
- UI placement: tab in the review page right panel — toggle between "Clinical Note" and "Patient Summary" tabs
- Generated as a second LLM call during the GPU handoff window (after SOAP extraction, before Whisper reload)
- Patient summary is editable before printing, same as the SOAP note
- Separate prompt from extraction — clinical precision and plain-language are contradictory writing styles

### Claude's Discretion
- Exact keyword patterns for assistant classification (informed by the categories above)
- How to structure the template-specific prompt overlays (Jinja2 template composition, string concatenation, etc.)
- hotwords parameter format and which terms get hotwords vs initial_prompt
- Patient summary prompt engineering (reading level, tone, structure)
- Print page HTML layout and styling
- How the manual vocab file is loaded and merged at startup
- Error handling when template auto-detection confidence is low

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DENTAL_INITIAL_PROMPT` in `transcription/whisper_service.py` (lines 24-53): 52-line dental vocabulary, ~200 tokens — needs expansion
- `speaker.py` keyword classifier (lines 10-62): 26 doctor patterns, 19 patient patterns — extend with assistant patterns
- `SPEAKER_SYSTEM_PROMPT` in `clinical/speaker.py` (lines 18-40): LLM re-attribution for 2 roles — enhance for 3 roles
- `EXTRACTION_SYSTEM_PROMPT` in `clinical/prompts.py` (lines 55-193): monolithic SOAP prompt with CDT reference — needs template composition layer
- `SoapNote` model in `clinical/models.py` (lines 25-76): has subjective, objective, assessment, plan, cdt_codes, clinical_discussion, medications, va_narrative
- `ClinicalExtractor.extract_with_gpu_handoff()` in `clinical/extractor.py` (lines 66-82): Whisper unload -> LLM -> LLM unload -> Whisper reload — patient summary call fits between extract() and ollama unload
- `OllamaService.generate_structured()`: structured output with Pydantic schema validation
- `Settings` in `config.py`: pydantic-settings with `DENTAL_` env prefix

### Established Patterns
- FastAPI + HTMX with Jinja2 templates and SSE streaming
- Routes return HTML partials for HTMX swaps
- GPU handoff pattern: sequential model loading within finally block for safety
- Pydantic models for all structured data with JSON schema for Ollama
- `ollama.Client` sync API (not async)
- `/nothink` prefix prepended to all user content for Qwen3

### Integration Points
- Template selection UI integrates into the recording start flow (dropdown before Record button)
- Template type stored in `SavedSession` metadata (new field in `session/store.py`)
- Template-specific hotwords passed to `WhisperService.transcribe()` via new parameter
- Patient summary generated in `extract_with_gpu_handoff()` after SOAP extraction
- Patient summary stored in `ExtractionResult` or `SavedSession` (new field)
- Review page right panel gets tab navigation (Clinical Note / Patient Summary)
- Print button on Patient Summary tab opens browser print dialog

</code_context>

<specifics>
## Specific Ideas

- All 4 assistant speech categories (instruments, comfort, procedural assists, charting) are equally important — the classifier should cover all of them
- The dentist specifically wants expanded vocabulary for: procedures, materials, surfaces, pathology, anatomy, findings, AND diagnoses — not just tooth numbers (which v1 already handles well)
- Manual vocab file approach for learn-as-you-go is intentionally simple — a plain text file the dentist can open in Notepad and add terms to
- Template auto-detection should use the first portion of transcript to infer appointment type, falling back to "General" if uncertain
- Patient summary should feel like something you'd hand to a patient who says "what did you just do?" — conversational, not clinical

</specifics>

<deferred>
## Deferred Ideas

- Auto-detection of vocab corrections from review screen edits — v3 enhancement (noted during vocabulary discussion)
- Audio-based speaker embeddings via resemblyzer — only if text-based 3-way classifier proves insufficient in practice
- Per-office configurable vocabulary — rejected for v2 in favor of baked-in, but could be revisited
- Hygienist as a 4th speaker role — for now, treated same as assistant

</deferred>

---

*Phase: 04-clinical-intelligence*
*Context gathered: 2026-03-29*
