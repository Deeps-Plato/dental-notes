# Feature Research: Dental Notes v2.0 Production & Clinical

**Domain:** Ambient clinical documentation for dental practices
**Researched:** 2026-03-28
**Confidence:** HIGH (dental workflow patterns well-documented; speaker diarization on constrained GPU is the main risk area)

## Context: What v1.0 Already Delivers

These features are built, tested (249 tests passing), and working. v2.0 builds on top of them.

| Built Feature | Implementation |
|---------------|----------------|
| Streaming audio capture + VAD + chunking | `audio/capture.py`, `audio/vad.py`, `transcription/chunker.py` |
| Local Whisper transcription with dental vocab | `transcription/whisper_service.py` (DENTAL_INITIAL_PROMPT, ~200 tokens) |
| Speaker labels (Doctor/Patient) via keywords + LLM | `session/speaker.py` (keyword), `clinical/speaker.py` (LLM re-attribution) |
| SOAP note extraction with CDT codes via Ollama/Qwen3 | `clinical/extractor.py`, `clinical/prompts.py`, `clinical/models.py` |
| GPU handoff (Whisper unload -> LLM -> Whisper reload) | `clinical/extractor.py` extract_with_gpu_handoff() |
| Side-by-side review UI + editing + clipboard copy | `ui/routes.py`, HTMX templates |
| Session save/load + list with status badges + finalize | `session/store.py`, `session/manager.py` |
| Dictation on any editable field via Whisper | `ui/dictation.py` |
| Audio discarded after transcription (AUD-01) | SessionManager._processing_loop() |
| Transcript deleted after note finalization (AUD-02) | SessionStore.finalize_session() |

## Feature Landscape

### Table Stakes (Users Expect These)

Features that any production ambient dental documentation tool must have. Missing these means the product cannot survive a real clinical day.

| Feature | Why Expected | Complexity | Depends On (v1) | Notes |
|---------|--------------|------------|------------------|-------|
| **Batch recording workflow** | Dentists see 5-10 patients/day. Manual start/stop per patient is friction that kills adoption. Freed, Denti.AI, and VideaAI all support multi-encounter sessions. | MEDIUM | SessionManager state machine, SessionStore | Requires a queue/list of sessions, not just one active session. The session concept shifts from "one recording" to "one patient encounter within a day." |
| **Auto-pause/resume on silence** | Between patients there is a 5-15 minute gap (room turnover, seating, chart review). The tool must not record dead air or hallway conversation. Every commercial ambient scribe handles this. | MEDIUM | VAD (vad.py), SessionManager pause/resume | Existing VAD + silence_gap_secs config provides the detection primitive. Need a longer "inter-patient silence" threshold (e.g., 3-5 minutes of continuous silence) distinct from intra-appointment pauses. |
| **Error recovery** | GPU crashes, mic disconnects, and Ollama failures happen in production. The tool must not lose a patient's transcript when the GPU OOMs during extraction. Commercial tools handle this silently. | MEDIUM | All pipeline components | Must handle: (1) Whisper crash mid-transcription, (2) mic USB disconnect, (3) Ollama unresponsive, (4) VRAM exhaustion during GPU handoff. Session data must be persisted before any risky operation. |
| **Expanded Whisper dental vocabulary** | v1 has a solid initial_prompt but it covers roughly 40% of terms a general dentist uses daily. Missing terms like specific anesthetic names, impression materials, cement brands, diagnostic findings, and periodontal descriptors cause Whisper to hallucinate or misspell. | LOW | WhisperService.DENTAL_INITIAL_PROMPT | Pure prompt expansion -- no code architecture change. The main risk is the initial_prompt token limit (Whisper uses only the first ~224 tokens, resetting per 30s segment). Must be strategic about which terms appear. |

### Differentiators (Competitive Advantage)

Features that set this tool apart from commercial alternatives. These are not expected but deliver outsized value.

| Feature | Value Proposition | Complexity | Depends On (v1) | Notes |
|---------|-------------------|------------|------------------|-------|
| **Appointment-type templates** | Different procedure types produce radically different notes. A crown prep note needs anesthetic details, material selection, shade, and lab info. A hygiene recall needs probing depths, BOP, and home care. Commercial tools like Freed use one generic template; Dentrix Ascend has 20+ procedure-specific templates. Matching Dentrix template specificity in an ambient tool is a genuine differentiator. | MEDIUM | ClinicalExtractor, EXTRACTION_SYSTEM_PROMPT, SoapNote model | Requires per-template system prompts and Pydantic models. Template selection can be manual (dropdown) or auto-detected from transcript content. Start with 5 core types. |
| **3-way speaker identification** | Most ambient scribes handle 2 speakers (doctor + patient). Dental offices routinely have a dental assistant present who hands instruments, suctions, and communicates with both doctor and patient. Correctly attributing assistant speech prevents contamination of the clinical note. | HIGH | speaker.py keyword classifier, clinical/speaker.py LLM re-attribution | This is the hardest v2 feature. Pyannote needs 6-8GB VRAM (exceeds GTX 1050 4GB minimum). Alternatives: (1) `diarize` library (CPU-only, Apache 2.0, 10.8% DER), (2) keyword-based 3-class classifier extending v1 patterns, (3) hybrid: keyword classifier + LLM re-attribution with 3 roles. |
| **Plain-language patient summary** | After-visit summaries (AVS) are an emerging standard in dentistry (NAM 2023 perspective paper). Generating a 6th-grade reading level summary alongside the clinical SOAP note enables patient handouts. No commercial dental ambient tool does this yet. | LOW | ClinicalExtractor, OllamaService | Second LLM pass on the same transcript with a patient-facing prompt. Low complexity because the extraction pipeline already exists -- just add a second prompt and output model. |
| **Windows installer + auto-start** | No pip install, no command line. Click an installer, machine boots, server starts. This is table stakes for deployment but a differentiator for local-first tools (Freed etc. are cloud -- no installer needed). | MEDIUM | start_server.py, setup_windows.py | PyInstaller or Inno Setup. Auto-start via Windows Task Scheduler or registry Run key. Already partially prototyped in setup_windows.py. |
| **Multi-machine deployment** | Replicating across operatory PCs without IT support. Copy installer + config, done. | LOW | Windows installer | Once installer exists, this is mostly documentation + a shared config file for Ollama host, model preferences, etc. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real-time SOAP note streaming** | "I want to see the note form as the conversation happens." | LLM extraction requires full conversation context. Streaming partial SOAP notes from incomplete transcripts produces inaccurate, hallucinated content that must be fully regenerated anyway. Also, GPU handoff (Whisper unload -> LLM -> reload) during active recording would create transcription gaps. | Keep current design: record first, extract after stop. The post-stop extraction is fast (10-30s with Qwen3 8B). |
| **Automatic Dentrix integration via API** | "I want notes to flow directly into Dentrix." | Dentrix's API is proprietary, poorly documented, requires per-practice licensing, and varies by version. Integration is fragile and version-dependent. Dentrix API access requires a separate agreement with Henry Schein. | Keep clipboard copy workflow. It works, it is reliable, and Deep explicitly scoped API integration out for v2. |
| **Full speaker diarization with pyannote on GPU** | "Just use pyannote for speaker ID, it is state of the art." | Pyannote 3.1 requires 6-8GB VRAM minimum. GTX 1050 has 4GB. Even GTX 1070 Ti has 8GB but must share with Whisper and Ollama. Loading pyannote alongside Whisper would OOM on target hardware. | Use `diarize` library (CPU-only, Apache 2.0, ~10.8% DER, 8x realtime on CPU) for embedding-based diarization, OR extend keyword classifier to 3 roles + LLM re-attribution. See 3-way speaker ID section below. |
| **Fine-tuning Whisper on dental data** | "Fine-tune Whisper for dental vocabulary instead of using initial_prompt." | Requires curated dental audio dataset (hundreds of hours), GPU training infrastructure, and ongoing maintenance when Whisper updates. The initial_prompt approach achieves 40-60% WER reduction on domain-specific terms without any training. Fine-tuning is a research project, not a product feature. | Expand initial_prompt strategically. Rotate vocabulary across segments if token limit is a concern. |
| **Continuous ambient recording (always-on)** | "Just leave it recording all day, automatically." | Florida is a two-party consent state. Recording without explicit per-patient consent is illegal. Always-on recording also captures private staff conversations, phone calls, and other patients in adjacent operatories. Storage and processing costs scale linearly. | Batch workflow with explicit start/stop per patient, auto-pause between patients. Consent obtained per patient. |
| **Voice commands during recording** | "Say 'new section' to mark SOAP boundaries." | Adds complexity to the transcription pipeline (must distinguish commands from clinical speech). Commands contaminate the transcript. Whisper has no reliable way to detect intent vs. content. | Let the LLM handle section boundaries during extraction. It already does this well in v1. |

## Feature Deep Dives

### 1. Batch Recording Workflow

**What it is:** A "clinic day" mode where the dentist starts the system in the morning and records multiple patient encounters throughout the day, reviewing and finalizing notes at end of day (or between patients during breaks).

**How commercial tools do it:**
- Freed: Tap "Capture Conversation" per encounter; notes queue up for review
- Denti.AI: Ambient mode with explicit start/stop per patient
- VideaAI Voice Notes: Continuous ambient with per-encounter segmentation

**Recommended approach for dental-notes:**
1. Add a `BatchSession` concept that manages a list of individual `PatientEncounter` sessions
2. UI shows a patient encounter list with status badges (recording / paused / needs review / finalized)
3. "Next Patient" button auto-stops current encounter + auto-starts new one
4. All encounters persist to disk immediately (crash recovery)
5. End-of-day review queue shows all encounters needing attention

**Expected UX flow:**
```
Morning: Start Clinic Day
  Patient 1: [Record] -> [Stop] -> encounter saved
  (silence gap / room turnover)
  Patient 2: [Record] -> [Stop] -> encounter saved
  ...
  End of day: Review queue -> edit notes -> copy to Dentrix -> finalize all
```

**Depends on (v1):** SessionManager, SessionStore, SavedSession model, review routes
**Complexity:** MEDIUM -- mostly UI and session management orchestration
**Key risk:** Session data loss if system crashes mid-day. Mitigation: write session to disk on every state transition.

### 2. Auto-Pause/Resume Between Patients

**What it is:** Silence-based detection of "no one is in the room" to automatically pause recording between patients, and resume when speech starts again.

**How it works technically:**
1. VAD already detects speech vs. silence at the chunk level (vad.py, silence_gap_secs=1.5s)
2. Add a longer "inter-patient silence" threshold: if VAD detects continuous silence for N minutes (configurable, default 3 minutes), auto-pause the current encounter
3. When speech resumes after auto-pause, prompt the user: "New patient detected. Start new encounter?" or auto-start based on configuration
4. The silence detection uses the same Silero VAD model already loaded

**Critical design decision:** Auto-pause is safe. Auto-resume into a NEW encounter requires care:
- Option A (recommended): Auto-pause, then require manual "Next Patient" to start new encounter. Safest for consent workflow (Florida two-party consent).
- Option B: Auto-pause, auto-resume into same encounter. Risky -- catches cleanup conversation.
- Option C: Auto-pause, detect new speech, ask user via UI notification. Good middle ground.

**Depends on (v1):** VadDetector, SessionManager pause/resume, AudioCapture
**Complexity:** MEDIUM -- the detection is simple (timer on consecutive silent frames); the UX decision (auto vs. prompted) is the hard part
**Key risk:** False positives during long silent procedures (e.g., impression setting for 5 minutes, rubber dam placement). Mitigation: configurable threshold + manual override always available.

### 3. Appointment-Type Templates

**What it is:** Different note structures optimized for specific dental procedures, rather than one generic SOAP template for all encounters.

**Core template types (start with these 5):**

| Template | Key Sections Beyond Standard SOAP | Trigger Terms |
|----------|----------------------------------|---------------|
| **Comprehensive Exam** (D0150) | Extra-oral exam, intra-oral soft tissue, hard tissue charting, risk assessment (caries/perio/cancer), treatment plan overview | "new patient", "comprehensive", "full exam" |
| **Restorative** (D2xxx) | Anesthetic details (type, amount, epi concentration, site), prep details, material/shade selection, bonding system, occlusal adjustment, post-op instructions | "composite", "filling", "crown prep", "onlay" |
| **Hygiene/Recall** (D1110, D0120) | Probing depths, BOP, calculus assessment, home care instructions, fluoride application, next recall interval | "cleaning", "prophy", "recall", "hygiene" |
| **Endodontic** (D3xxx) | Working lengths, file sizes, irrigation protocol, obturation material, temporary restoration, referral details | "root canal", "endo", "pulpitis", "access" |
| **Oral Surgery** (D7xxx) | Surgical technique, hemostasis, socket preservation, suture type/count, post-op medications, follow-up schedule | "extraction", "surgical", "impacted", "bone graft" |

**Implementation approach:**
1. Each template is a system prompt variant + a Pydantic model with template-specific optional fields
2. Template selection: manual dropdown (most reliable) with optional auto-detection from first 30s of transcript
3. The base SoapNote model gains optional template-specific sections (anesthetic_details, probing_data, etc.)
4. v1's EXTRACTION_SYSTEM_PROMPT becomes the "General" template; template-specific prompts extend it
5. Template-specific CDT code subsets reduce hallucinated code suggestions

**Dentrix Ascend reference templates (from official docs):** Amalgam restoration, Composite restoration, Crown & bridge, Crown prep, Crown seat, Denture, Endodontic, Extraction, Implant, Inlay/Onlay, Orthodontic, Periodontal, Prophy, Sealant, Whitening. Our 5 core templates cover the highest-frequency categories; the rest can be added incrementally.

**Depends on (v1):** ClinicalExtractor, EXTRACTION_SYSTEM_PROMPT, SoapNote model, ExtractionResult
**Complexity:** MEDIUM -- prompt engineering + model extension, not new infrastructure
**Key risk:** Template auto-detection accuracy. Mitigation: always allow manual override; auto-detection is a convenience, not a requirement.

### 4. Three-Way Speaker Identification

**What it is:** Distinguishing Doctor, Patient, and Dental Assistant in the transcript, rather than just Doctor/Patient.

**Why 3 speakers matters in dental:**
- Assistant hands instruments, operates suction, takes impressions, applies materials
- Assistant communicates procedural status ("isolation complete", "impression set", "suction ready")
- Assistant talks to patient ("you're doing great", "rinse and spit")
- Misattributing assistant speech to Doctor contaminates the clinical note with non-clinical directives
- Misattributing assistant speech to Patient adds false symptom reports

**Dental assistant speech patterns (keyword classifier extension):**
```python
_ASSISTANT_PATTERNS = [
    r"\b(?:suction|retract|pass me|hand me|mix|prep the|tray)\b",
    r"\b(?:rinse|spit|you'?re doing (?:great|good)|almost done)\b",
    r"\b(?:isolation|rubber dam|clamp|matrix band|wedge|retraction cord)\b",
    r"\b(?:light cure|etch|bond|pack|condense|polish|finish)\b",
    r"\b(?:ready|set up|break down|sterilize|chart|next patient)\b",
    r"\b(?:doctor|Dr\.)\s+(?:said|wants|needs|asked)\b",
]
```

**Technical approach -- tiered strategy:**

**Tier 1 (recommended for v2, LOW complexity):** Extend keyword classifier to 3 classes
- Add `_ASSISTANT_PATTERNS` to `session/speaker.py`
- `classify_speaker()` returns "Doctor", "Patient", or "Assistant"
- LLM re-attribution prompt (clinical/speaker.py) updated for 3 roles
- No new dependencies, works on all hardware
- Estimated effort: 1-2 days

**Tier 2 (stretch goal, MEDIUM complexity):** CPU-based embedding diarization
- Use `diarize` library (Apache 2.0, CPU-only, 10.8% DER, 8x realtime on CPU)
- Install: `pip install diarize` (uses Silero VAD + WeSpeaker ResNet34 via ONNX)
- Produces speaker segments as "Speaker 0", "Speaker 1", "Speaker 2"
- Map speaker IDs to roles using keyword classifier on each segment's text
- Post-recording batch process (not real-time): ~75 seconds for 10-minute recording
- Limitation: cannot handle simultaneous/overlapping speech, struggles with utterances under 0.4s
- Adds ~75s post-processing before extraction (acceptable for end-of-day review workflow)

**Tier 3 (future, HIGH complexity):** GPU-based diarization
- Pyannote 3.1 requires 6-8GB VRAM -- NOT viable on GTX 1050 4GB minimum hardware
- WhisperX integration provides word-level timestamps + diarization in one pass
- Would require GPU handoff: Whisper unload -> pyannote load -> diarize -> pyannote unload -> Whisper reload
- Only viable on GTX 1070 Ti (8GB) or better

**Recommendation:** Ship Tier 1 (keyword extension) in v2.0. Evaluate Tier 2 (diarize library) as a v2.x enhancement. Tier 3 is only viable on higher-end hardware.

**Depends on (v1):** session/speaker.py (keyword classifier), clinical/speaker.py (LLM re-attribution), SessionManager chunks
**Complexity:** Tier 1 = LOW, Tier 2 = MEDIUM, Tier 3 = HIGH
**Key risk:** Diarization accuracy in noisy dental environment with overlapping speech. Dental procedures create background noise (drills, suction, ultrasonic scalers) that degrades audio-based speaker identification. Mitigation: keyword classifier operates on already-transcribed text (not audio), so it is noise-resistant.

### 5. Expanded Whisper Dental Vocabulary

**What it is:** A comprehensive initial_prompt covering the full range of dental terminology a general practitioner encounters.

**Current coverage (v1 DENTAL_INITIAL_PROMPT):**
- Tooth numbering (Universal 1-32)
- Surface abbreviations (MOD, DO, BL, etc.)
- Basic restorative terms (composite, amalgam, crown, bridge)
- Basic perio terms (prophy, SRP, pocket depth)
- Basic endo terms (pulpectomy, root canal, gutta-percha)
- Some materials/brands (Shofu, Ivoclar, Filtek, RelyX)
- A few CDT codes
- Total: ~200 tokens, approaching the ~224 token effective limit

**Gaps to fill for v2:**

| Category | Missing Terms (HIGH priority) |
|----------|-------------------------------|
| **Anesthetics** | lidocaine, articaine, Septocaine, mepivacaine, Carbocaine, epinephrine, 1:100,000, 1:200,000, inferior alveolar nerve block, infiltration, long buccal, mental block, PSA, MSA, ASA |
| **Impression/Cement** | alginate, polyvinyl siloxane, PVS, polyether, Impregum, Aquasil, TempBond, RelyX Unicem, glass ionomer cement, RMGI, zinc phosphate |
| **Restorative Details** | prep, margin, shoulder, chamfer, ferrule, buildup, post and core, fiber post, shade A1 A2 A3 B1 B2, Vita shade guide |
| **Perio Expanded** | clinical attachment loss, CAL, bone loss, vertical defect, horizontal bone loss, gingival index, Arestin, Atridox, chlorhexidine, Peridex |
| **Oral Surgery** | elevation, luxation, forceps, rongeur, bone file, socket, granulation tissue, primary closure, PRF, platelet-rich fibrin, collagen plug, Gelfoam, Surgicel |
| **Prosthetics** | RPD, removable partial denture, clasp, rest, framework, reline, rebase, bite registration, facebow, centric relation, vertical dimension |
| **Imaging/Diagnostics** | CBCT, cone beam, radiopaque, radiolucent, PDL widening, lamina dura, periapical pathology |
| **Pathology/Findings** | attrition, abrasion, erosion, abfraction, cervical lesion, white spot lesion, demineralization, hypoplasia, fluorosis, lichen planus, leukoplakia |
| **Anatomy** | premolar, bicuspid, quadrant, sextant, arch, palate, floor of mouth, vestibule, frenum, alveolar ridge |

**Critical constraint:** Whisper's `initial_prompt` is limited to ~224 tokens. Strategy:
1. **Prioritize terms Whisper misspells most** -- brand names (Septocaine, Impregum), abbreviations (CAL, RMGI, PVS), and numerical patterns (tooth numbers, shade codes)
2. **Group semantically** -- Whisper benefits from contextual clusters ("Anesthetic: lidocaine, articaine, Septocaine. Infiltration, nerve block.")
3. **Template-specific rotation** -- If appointment templates are built first, rotate the initial_prompt to include template-relevant terms (e.g., restorative template emphasizes materials/shades; perio template emphasizes probing/attachment terms)
4. **The prompt resets per 30s segment** -- every segment gets the same prompt benefit, so the rotation strategy works across an entire appointment

**Implementation plan:**
1. Audit current prompt for token count and identify low-value terms to remove
2. Create a base prompt (~150 tokens) covering universally needed terms
3. Create template-specific extensions (~70 tokens each) for the remaining budget
4. A/B test transcription accuracy on recorded dental conversations with old vs. new prompts

**Depends on (v1):** WhisperService, DENTAL_INITIAL_PROMPT
**Complexity:** LOW -- text editing, no architecture change
**Key risk:** Token limit means trade-offs. Testing required to measure which terms actually improve transcription vs. which are already handled well by Whisper base vocabulary.

### 6. Plain-Language Patient Summary

**What it is:** A non-clinical, 6th-grade reading level summary of what happened during the visit, suitable for printing as a patient handout or after-visit summary (AVS).

**What research says (NAM 2023 perspective, dental AVS studies):**
- AVS should include: patient name, provider contact, visit date, reason for visit, procedures performed, follow-up instructions, medications prescribed
- Written in plain language at 6th-grade reading level
- Culturally appropriate and health-literacy-aware
- Dental AVS should exclude irrelevant medical sections (immunizations, lab results)
- 85.6% AVS compliance among dental students using EHR-based modules (2025 study)
- Modified AVS with plain language and white space layouts associated with higher use and usefulness

**Recommended implementation:**
1. Add a `PATIENT_SUMMARY_PROMPT` that instructs the LLM to:
   - Summarize the visit in 3-5 sentences using no clinical jargon
   - Explain any diagnoses in plain terms ("You have a cavity on your back molar")
   - List what was done today in simple language
   - List follow-up instructions clearly
   - Avoid abbreviations, CDT codes, and technical tooth numbers (use "upper right back tooth" instead of "#3")
2. Add a `patient_summary: str` field to `ExtractionResult`
3. Generate during the same extraction pass (single LLM call with both SOAP + summary in the JSON schema)
4. Display in review UI alongside SOAP note with a "Print for Patient" button

**Example output:**
> "Today Dr. Chadda examined your upper right back tooth that has been bothering you. He found a crack in the old filling and some decay underneath it. The plan is to remove the old filling, clean out the decay, and place a new tooth-colored filling at your next visit on [date]. If the decay goes deeper than expected, you may need a crown instead. Please avoid chewing hard foods on that side until your next appointment. Call us at [number] if you have any pain or swelling."

**Depends on (v1):** ClinicalExtractor, OllamaService, ExtractionResult model, review UI templates
**Complexity:** LOW -- one additional prompt section + one new model field + minor UI addition
**Key risk:** LLM quality at 6th-grade readability. Qwen3 8B can produce plain language but may need prompt iteration for consistent reading level. Mitigation: prompt includes explicit reading level instruction + examples.

## Feature Dependencies

```
[Error Recovery]
    |-- foundational for --> [Batch Recording Workflow]
    |-- foundational for --> [All production features]

[Batch Recording Workflow]
    |-- requires --> [Error Recovery] (batch loses more data on crash)
    |-- enhances --> [Auto-Pause/Resume] (auto-pause between patients in batch)

[Auto-Pause/Resume]
    |-- requires --> [VAD (v1)] (silence detection primitive)
    |-- enhances --> [Batch Recording Workflow]

[Appointment Templates]
    |-- requires --> [ClinicalExtractor (v1)] (extraction pipeline)
    |-- enhances --> [Expanded Vocabulary] (template-specific vocab rotation)
    |-- enhances --> [Patient Summary] (template-specific summary language)

[3-Way Speaker ID (Tier 1)]
    |-- requires --> [speaker.py keyword classifier (v1)]
    |-- requires --> [clinical/speaker.py LLM re-attribution (v1)]
    |-- independent of --> [Batch Recording] (works per-encounter)

[Expanded Vocabulary]
    |-- requires --> [WhisperService (v1)]
    |-- enhances --> [3-Way Speaker ID] (better transcription -> better keywords)
    |-- enhances --> [Appointment Templates] (template-specific prompt rotation)

[Patient Summary]
    |-- requires --> [ClinicalExtractor (v1)]
    |-- enhances --> [Appointment Templates] (template-specific summary language)
    |-- independent of --> [Speaker ID, Batch, Auto-Pause]

[Windows Installer]
    |-- requires --> [Error Recovery] (production deployment needs robustness)
    |-- independent of --> [all clinical features]

[Auto-Start on Boot]
    |-- requires --> [Windows Installer]

[Multi-Machine Deployment]
    |-- requires --> [Windows Installer]
```

### Dependency Notes

- **Error Recovery is the foundation:** A full clinic day of 5-10 encounters is far more valuable than a single encounter. Losing a batch to a crash is catastrophic. Error recovery must be in place before batch mode ships.
- **Auto-Pause enhances Batch Recording:** Auto-pause is optional but dramatically improves the batch UX. Can ship batch without auto-pause (manual Next Patient button), then add auto-pause as a refinement.
- **Appointment Templates enhance Expanded Vocabulary:** If templates exist, the Whisper initial_prompt can rotate to include template-specific terms, working around the 224-token limit.
- **3-Way Speaker ID is independent of Batch:** Speaker identification works per-encounter. It does not depend on batch mode or auto-pause.
- **Patient Summary is the most independent feature:** Requires only the existing extraction pipeline. Can be built at any time.

## MVP Definition (v2.0 Milestone)

### Must Ship (P1)

- [ ] **Error recovery** -- GPU crashes, mic disconnects, Ollama failures handled gracefully. Sessions never lost. This is the prerequisite for everything else.
- [ ] **Batch recording workflow** -- Multiple encounters per clinic day with encounter list, status tracking, end-of-day review queue. This is the core workflow change for production use.
- [ ] **Expanded Whisper vocabulary** -- Fill the gaps in anesthetics, materials, perio, anatomy, and diagnostics. Low effort, high impact on transcription quality.
- [ ] **Appointment-type templates (3 core)** -- Comprehensive Exam, Restorative, and Hygiene/Recall. These cover ~80% of daily encounters.

### Should Ship (P2)

- [ ] **Auto-pause/resume** -- Silence-based auto-pause between patients. Enhances batch workflow but not required for it.
- [ ] **3-way speaker ID (Tier 1)** -- Keyword classifier extended to 3 roles + LLM re-attribution. Low complexity, meaningful improvement.
- [ ] **Patient summary** -- Plain-language AVS generation. Low complexity, high patient-facing value.
- [ ] **Windows installer** -- One-click deployment. Required for multi-machine rollout.
- [ ] **Remaining templates (Endo, Oral Surgery)** -- Complete the 5-template set.

### Defer to v2.x (P3)

- [ ] **Auto-start on boot** -- Nice for production but easy to add after installer exists
- [ ] **Multi-machine deployment** -- Documentation + shared config after installer
- [ ] **3-way speaker ID (Tier 2)** -- `diarize` library integration for embedding-based CPU diarization
- [ ] **Template auto-detection** -- Automatically select template from transcript content

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Phase Recommendation |
|---------|------------|---------------------|----------|---------------------|
| Error recovery | HIGH | MEDIUM | P1 | Phase 1 (foundation) |
| Batch recording workflow | HIGH | MEDIUM | P1 | Phase 1 (foundation) |
| Expanded Whisper vocabulary | HIGH | LOW | P1 | Phase 1 (foundation) |
| Appointment templates (3 core) | HIGH | MEDIUM | P1 | Phase 2 (clinical intelligence) |
| Auto-pause/resume | MEDIUM | MEDIUM | P2 | Phase 1 or 2 (enhances batch) |
| 3-way speaker ID (Tier 1) | MEDIUM | LOW | P2 | Phase 2 (clinical intelligence) |
| Patient summary | MEDIUM | LOW | P2 | Phase 2 (clinical intelligence) |
| Windows installer | HIGH | MEDIUM | P2 | Phase 3 (deployment) |
| Remaining templates | MEDIUM | LOW | P2 | Phase 2 (clinical intelligence) |
| Auto-start on boot | MEDIUM | LOW | P3 | Phase 3 (deployment) |
| Multi-machine deployment | MEDIUM | LOW | P3 | Phase 3 (deployment) |
| 3-way speaker ID (Tier 2) | LOW | MEDIUM | P3 | Future |
| Template auto-detection | LOW | MEDIUM | P3 | Future |

## Competitor Feature Analysis

| Feature | Freed AI | Denti.AI | VideaAI Voice Notes | Our Approach |
|---------|----------|----------|---------------------|--------------|
| Ambient recording | Cloud transcription, tap to start/pause | Cloud-based ambient | Ambient dental AI | Local Whisper, fully private |
| Batch workflow | Yes, encounters queue for review | Yes, per-patient | Yes | Encounter list + end-of-day review |
| Auto-pause | Manual pause/resume | Not documented | Not documented | Silence-based auto-pause (VAD) |
| Templates | Generic SOAP | Perio-specific workflows | Dental-specific | 5 procedure-specific templates |
| Speaker ID | 2 speakers (cloud AI) | Not documented | Not documented | 3 speakers via keyword + LLM (local) |
| Patient summary | Not documented | Not documented | Not documented | Plain-language AVS at 6th-grade level |
| Privacy | Cloud (HIPAA/BAA) | Cloud (HIPAA/BAA) | Cloud | 100% local, zero cloud dependency |
| Cost | $99-199/month/provider | Contact sales | Contact sales | Free (local processing) |
| Dentrix integration | EHR push (browser) | Not documented | Not documented | Clipboard copy |

**Key competitive advantages for v2.0:** No commercial dental ambient tool offers all three of: (1) fully local/private processing, (2) procedure-specific templates, and (3) plain-language patient summaries. The combination of privacy + clinical specificity + patient communication is a unique position in the market.

## Sources

### Ambient Clinical Documentation
- [Twofold: Best AI for Dental Clinical Notes (2026)](https://www.trytwofold.com/blog/best-ai-for-dental-clinical-notes-and-charting-2026) -- MEDIUM confidence
- [JMIR AI: Real-World Evidence of Digital Scribes](https://ai.jmir.org/2025/1/e76743) -- HIGH confidence, peer-reviewed
- [McKinsey: Ambient Scribing at a Crossroads](https://www.mckinsey.com/industries/healthcare/our-insights/ambient-scribing-at-the-crossroads-what-comes-next) -- MEDIUM confidence
- [PMC: Ambient AI Reduces Documentation Time](https://www.sciencedirect.com/science/article/abs/pii/S1479666X25001544) -- HIGH confidence, peer-reviewed
- [Freed AI: How to Use an AI Scribe](https://www.getfreed.ai/resources/how-to-use-an-ai-scribe) -- MEDIUM confidence

### Dental Note Templates
- [ADA: Templates, Smart Phrases and SOAP](https://www.ada.org/resources/practice/practice-management/templates-smart-phrases-and-soap) -- HIGH confidence, authoritative
- [Dentrix Ascend: Clinical Note Templates List](https://support.dentrixascend.com/hc/en-us/articles/229958387-Clinical-note-templates-list) -- HIGH confidence, industry standard
- [Kiroku: Dental Note Templates](https://www.trykiroku.com/blog/dental-note-templates-comprehensive-new-patient-exam) -- MEDIUM confidence
- [Dental SOAP Notes Guide (SoapNoteAI)](https://www.soapnoteai.com/soap-note-guides-and-example/dentistry/) -- MEDIUM confidence
- [TextExpander: Dental SOAP Notes Template (2025)](https://textexpander.com/templates/dental-soap-note-examples) -- MEDIUM confidence

### Speaker Diarization
- [Pyannote Speaker Diarization 3.1 (HuggingFace)](https://huggingface.co/pyannote/speaker-diarization-3.1) -- HIGH confidence, official model card
- [FoxNoseTech/diarize (GitHub)](https://github.com/FoxNoseTech/diarize) -- MEDIUM confidence, new library (March 2026), Apache 2.0, 10.8% DER
- [Picovoice Falcon Speaker Diarization](https://picovoice.ai/platform/falcon/) -- MEDIUM confidence, commercial with free tier
- [Brass Transcripts: Speaker Diarization Models Comparison (2026)](https://brasstranscripts.com/blog/speaker-diarization-models-comparison) -- MEDIUM confidence
- [WhisperX (GitHub)](https://github.com/m-bain/whisperX) -- HIGH confidence, open source

### Whisper Vocabulary Prompting
- [OpenAI: Whisper Prompting Guide](https://developers.openai.com/cookbook/examples/whisper_prompting_guide) -- HIGH confidence, official docs
- [Prompt Engineering in Whisper (Medium)](https://medium.com/axinc-ai/prompt-engineering-in-whisper-6bb18003562d) -- MEDIUM confidence
- [ai.dentist: Voice Recognition for Dental Notes](https://ai.dentist/blog/voice-recognition-for-dental-notes-beyond-dragon-s/) -- MEDIUM confidence

### Patient Summaries / After-Visit Summaries
- [NAM: After Visit Summaries for Dentistry](https://nam.edu/perspectives/after-visit-summaries-a-tool-whose-time-has-come-for-use-in-dentistry/) -- HIGH confidence, authoritative
- [PMC: Plain Language for After Visit Summaries](https://pmc.ncbi.nlm.nih.gov/articles/PMC4936874/) -- HIGH confidence, peer-reviewed
- [Dental Students AVS Study (2025)](https://onlinelibrary.wiley.com/doi/10.1002/jdd.13913) -- HIGH confidence, peer-reviewed

### Dental Terminology
- [ADA: Glossary of Dental Clinical Terms](https://www.ada.org/publications/cdt/glossary-of-dental-clinical-terms) -- HIGH confidence, authoritative
- [ADA: CDT Code on Dental Procedures and Nomenclature](https://www.ada.org/publications/cdt) -- HIGH confidence, authoritative

---
*Feature research for: Dental Notes v2.0 Production & Clinical*
*Researched: 2026-03-28*
