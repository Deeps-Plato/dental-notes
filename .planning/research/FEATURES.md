# Feature Research

**Domain:** Ambient clinical intelligence for dental practices
**Researched:** 2026-03-05
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Ambient audio recording** | Core promise of the product -- if it can't reliably capture appointment audio, nothing else works | HIGH | Requires microphone selection, noise handling in dental operatory (suction, handpieces, ultrasonic scalers), multi-speaker capture. Dental environment is noisier than a physician's office. |
| **Speech-to-text transcription** | The raw material for everything downstream; every competitor does this | HIGH | Whisper (faster-whisper) on local NVIDIA GPU. Must handle dental terminology (tooth numbers, surfaces, materials). Quality of transcript determines quality of everything else. |
| **Clinical content filtering** | Dental appointments are 60-70% social conversation/chitchat; notes should contain only clinical content | MEDIUM | LLM-based filtering to separate "how are the kids?" from "I see Class II decay on the mesial of 14." Competitors (VideaHealth, Denti.AI) highlight this as core capability. |
| **Structured SOAP note generation** | Industry-standard documentation format; all competitors generate SOAP notes | HIGH | Dental SOAP: Subjective (chief complaint, history, symptoms), Objective (clinical findings, radiographic findings, perio measurements), Assessment (diagnosis, prognosis), Plan (treatment plan, materials, follow-up). Must use proper tooth numbering (Universal notation) and surface descriptions. |
| **Review and edit workflow** | Every competitor requires clinician sign-off before finalization; no AI note goes straight to the record | MEDIUM | Side-by-side view: full transcript on left, structured SOAP draft on right. Inline editing of the draft. "Accept" or "Edit" per section. Must be fast -- under 60 seconds for review per note. |
| **One-click copy/export** | Dentist needs to get the final note into Dentrix quickly | LOW | Copy-to-clipboard of finalized note in a format that pastes cleanly into Dentrix's clinical notes field. No API integration needed for v1. |
| **Recording consent mechanism** | Florida is a two-party consent state (felony to record without consent); every cloud competitor has click-to-activate consent | LOW | Simple consent flow: before recording starts, system requires explicit activation. Florida Statute 934.03 -- violation is a third-degree felony (up to 5 years, $5,000 fine). Consent acknowledgment must be logged. |
| **Ephemeral data handling** | HIPAA and patient trust require that recordings/transcripts don't persist | MEDIUM | Audio and transcript are deleted after note is finalized and accepted. No permanent audio storage. This is a differentiator vs. cloud competitors (Overjet stores 7 years of encrypted audio). |
| **Session management** | Dentist sees 5-10 patients/day; needs to track which session is which | LOW | Start/stop recording per appointment. Basic metadata: date, time, duration. No patient name entry needed (privacy-first). |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Fully local/on-premise processing** | Zero cloud dependency -- no patient data ever leaves the office network. Every major competitor (Freed, Overjet Voice, Nuance DAX, VideaHealth, Bola, Denti.AI) is cloud-based SaaS. This is the primary differentiator. | HIGH | Requires local LLM for note generation (quality TBD during research). Local Whisper already proven via whisper-ptt. Trade-off: local LLM quality vs. GPT-4/Claude API quality. |
| **No per-use cost** | Cloud competitors charge $99-$399/month per provider (Freed ~$149/mo, Nuance DAX ~$199-399/mo). This tool has zero marginal cost after hardware investment. | LOW | Existing NVIDIA GPUs in the office are sufficient. No subscription, no per-encounter fee, no vendor lock-in. |
| **CDT procedure code suggestions** | Automated extraction of CDT codes from clinical conversation reduces coding errors and speeds billing. DentScribe patented template-to-CDT mapping. Overjet and OneChart offer this. | HIGH | Map clinical descriptions to CDT codes (e.g., "composite on the mesial of 14" -> D2391). Requires a CDT code database and mapping logic. Start with common procedures (~50-100 codes cover 90% of general dentistry). |
| **Speaker diarization** | Distinguishing dentist, hygienist, assistant, and patient improves note accuracy. Denti.AI does this with multi-speaker capture. | HIGH | Pyannote or similar local diarization. In dental: provider dictates findings, patient reports symptoms, hygienist reports measurements. Knowing who said what maps to correct SOAP sections (patient speech -> Subjective, provider speech -> Objective/Assessment). |
| **Voice-activated perio charting** | Hands-free perio data entry saves significant time for hygiene appointments. Bola Voice Perio and Overjet Voice offer this. | HIGH | Hygienist reads pocket depths ("3, 2, 3, 4, 5, 3") and system maps to tooth/site. Requires structured output matching 6-point-per-tooth format. Very high accuracy needed -- wrong numbers in perio charts are clinically dangerous. Defer to v2+. |
| **Dental terminology optimization** | Custom vocabulary for Whisper prompt (tooth numbers, materials, CDT procedures, dental conditions) dramatically improves transcription accuracy | MEDIUM | Similar to whisper-ptt's INITIAL_PROMPT approach. Build a dental-specific prompt containing common terms: "amalgam, composite, zirconia, crown prep, endodontic, periapical, bitewing, Class II, mesial, distal, buccal, lingual, occlusal, furcation, mobility grade, bleeding on probing." |
| **Appointment-type templates** | Different appointment types need different note structures (exam vs. crown prep vs. extraction vs. hygiene recall) | MEDIUM | Pre-configured templates: Comprehensive Exam, Periodic Exam, Hygiene/SRP, Restorative, Extraction, Emergency/Pain, Endo. User selects type before or after recording. Template determines which SOAP sections are emphasized and what CDT codes are suggested. |
| **Post-visit patient summary** | Plain-language summary of what was done and what's next, suitable for giving to the patient | LOW | Generated alongside the clinical note. Avoids jargon. "We placed a filling on your upper left first premolar. Please avoid chewing on that side for 24 hours." Freed and Nabla offer this as a feature. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real-time streaming transcript display** | Seems impressive and "high-tech"; some competitors show live transcription | Distracts the dentist during the appointment. If you're reading a screen while working on a patient, you're not focused on the patient. Dental work requires visual and manual attention. The whole point of ambient AI is to NOT look at a screen during the encounter. | Generate transcript and note post-appointment. Display only after recording stops. |
| **Dentrix API integration** | Automatic note insertion without copy-paste | Dentrix's API is proprietary, poorly documented, and requires a paid partnership. Henry Schein controls access. Integration is fragile and adds a massive dependency for minimal gain (saving one copy-paste). Competitors like Denti.AI integrate but they're companies with vendor agreements. | Copy-to-clipboard with Dentrix-friendly formatting. One paste. Fast enough. |
| **Patient identity/records database** | Link notes to named patients for history tracking | Creates a PHI database that must be secured, backed up, encrypted, and HIPAA-audited. Massive liability for a local tool. The purpose of this tool is note generation, not EHR replacement. Dentrix already stores patient records. | Notes are anonymous sessions. Dentist pastes into the correct patient record in Dentrix manually. The dentist already knows which patient they're seeing. |
| **Multi-location cloud sync** | Practice with multiple offices wants notes everywhere | Violates the local-only privacy principle. Cloud sync = data leaving the building. Also adds enormous infrastructure complexity for a single-dentist v1 tool. | Each operatory runs independently. Notes are finalized and pasted into Dentrix (which already handles multi-location). |
| **Continuous/always-on recording** | "Just leave it running all day" | Legal nightmare in a two-party consent state. Also generates enormous audio files, most of which is silence or non-patient conversation. Battery/storage concerns. | Explicit start/stop per appointment with consent acknowledgment. |
| **Autonomous note finalization** | "Why do I have to review? Just file it automatically" | AI hallucination is real and documented -- studies show 19.5% of transcript errors transmit to clinical notes. A wrong tooth number or missed allergy in an auto-filed note is a malpractice risk. Every competitor requires clinician review before finalization. | Fast review workflow that takes under 60 seconds. Make review so quick that skipping it isn't tempting. |
| **Insurance claim generation** | "Generate the claim from the note" | CDT code mapping for claims requires exact accuracy -- wrong codes mean denied claims, fraud allegations, or insurance audits. The gap between "suggested codes" and "filed claims" is where liability lives. | Suggest CDT codes as a reference. Dentist/billing staff enters them into Dentrix for claim submission through normal channels. |
| **Mobile/tablet recording app** | "I want to use my phone as the mic" | Phone microphones are low quality for ambient room recording. Phone introduces distraction in the operatory. Also adds cross-platform development complexity (iOS/Android). The previous failed attempt at this project was a Flutter mobile app. | Dedicated USB/Bluetooth conference mic or lavalier mic connected to the operatory workstation. |
| **Voice-activated perio charting in v1** | Hands-free perio is highly requested by hygienists | Perio charting requires extremely high accuracy (wrong pocket depth = wrong treatment plan). Structured numeric data ("3, 2, 3, 4, 5, 3" mapped to specific teeth and sites) is harder than free-text transcription. Needs its own validation and testing cycle. | Defer to v2. Get core ambient note-taking working reliably first. Add voice perio as a separate feature once transcription accuracy is proven. |

## Feature Dependencies

```
[Audio Recording]
    |
    +--requires--> [Microphone Hardware Selection]
    |
    +--produces--> [Raw Audio]
                       |
                       +--requires--> [Speech-to-Text Transcription]
                                          |
                                          +--produces--> [Raw Transcript]
                                                             |
                                                             +--requires--> [Clinical Content Filtering]
                                                             |                  |
                                                             |                  +--produces--> [Filtered Clinical Content]
                                                             |                                     |
                                                             |                                     +--requires--> [SOAP Note Generation]
                                                             |                                     |                  |
                                                             |                                     |                  +--enhances--> [CDT Code Suggestions]
                                                             |                                     |                  |
                                                             |                                     |                  +--enhances--> [Appointment-Type Templates]
                                                             |                                     |
                                                             |                                     +--enhances--> [Patient Summary Generation]
                                                             |
                                                             +--enhances--> [Speaker Diarization]
                                                                                |
                                                                                +--enhances--> [Clinical Content Filtering]

[SOAP Note Generation]
    |
    +--requires--> [Review & Edit Workflow]
                       |
                       +--requires--> [Copy/Export to Clipboard]
                                          |
                                          +--triggers--> [Ephemeral Data Cleanup]

[Recording Consent Mechanism] --requires--> [Audio Recording] (must happen BEFORE recording starts)

[Session Management] --enhances--> [Audio Recording] (tracks start/stop/metadata)

[Dental Terminology Optimization] --enhances--> [Speech-to-Text Transcription]

[Voice Perio Charting] --requires--> [Speaker Diarization] + [Speech-to-Text Transcription]
    (v2+ feature, conflicts with v1 scope)
```

### Dependency Notes

- **Recording requires consent:** In Florida (two-party consent state), the consent mechanism MUST fire before any audio capture begins. This is a legal hard dependency, not a UX preference.
- **SOAP note generation requires clinical filtering:** Without filtering, notes would contain "so how was your vacation?" alongside "Class II on the DO of 19." Filtering is not optional.
- **Speaker diarization enhances filtering:** Knowing who said what helps map speech to correct SOAP sections, but filtering can work without it (just with lower accuracy). Diarization is an enhancement, not a hard dependency.
- **CDT code suggestions require SOAP notes:** Codes are derived from the Assessment and Plan sections. Cannot suggest codes without structured clinical content.
- **Ephemeral cleanup requires finalization:** Audio and transcript deletion is triggered by the dentist accepting/finalizing the note. Cannot delete before review is complete.
- **Voice perio conflicts with v1 scope:** Adding perio charting before core note-taking is reliable would dilute focus and delay delivery. Sequential, not parallel.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what's needed to validate that ambient dental note-taking works locally.

- [ ] **Ambient audio recording** -- Start/stop recording of dental appointment via operatory workstation
- [ ] **Recording consent gate** -- Cannot start recording without explicit consent acknowledgment (Florida law)
- [ ] **Local Whisper transcription** -- faster-whisper on NVIDIA GPU with dental terminology prompt
- [ ] **Clinical content filtering** -- Local LLM separates clinical speech from chitchat
- [ ] **SOAP note generation** -- Structured dental SOAP note from filtered content
- [ ] **Side-by-side review UI** -- Full transcript + SOAP draft, editable, accept/reject per section
- [ ] **Copy to clipboard** -- One-click copy of finalized note, formatted for Dentrix paste
- [ ] **Ephemeral data cleanup** -- Delete audio and transcript after note is finalized
- [ ] **Session management** -- Start/stop/list today's sessions with basic metadata

### Add After Validation (v1.x)

Features to add once core note-taking is proven reliable in real appointments.

- [ ] **CDT code suggestions** -- Extract likely CDT codes from Assessment/Plan sections (trigger: core notes working reliably for 2+ weeks)
- [ ] **Appointment-type templates** -- Pre-configured templates for exam, restorative, hygiene, endo, extraction (trigger: user friction with one-size-fits-all template)
- [ ] **Dental terminology Whisper prompt** -- Expanded custom vocabulary for better transcription accuracy (trigger: recurring transcription errors on dental terms)
- [ ] **Speaker diarization** -- Distinguish dentist/hygienist/patient voices for better section mapping (trigger: filtering accuracy issues due to speaker confusion)
- [ ] **Post-visit patient summary** -- Plain-language summary for patient handoff (trigger: user requests this workflow)

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Voice-activated perio charting** -- Hands-free pocket depth entry mapped to 6-point charts (why defer: requires extremely high numeric accuracy, separate validation cycle)
- [ ] **Multi-provider support** -- Multiple dentists/hygienists using the system simultaneously (why defer: single-dentist validation first)
- [ ] **Referral letter generation** -- Auto-generate specialist referral letters from clinical notes (why defer: nice-to-have, not core workflow)
- [ ] **Treatment plan generation** -- Structured treatment plan with sequencing and estimated costs (why defer: high complexity, liability concerns)
- [ ] **Recording consent law reference** -- Built-in state-by-state recording consent guide (why defer: a PDF reference document suffices; not a software feature)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Ambient audio recording | HIGH | HIGH | P1 |
| Recording consent gate | HIGH | LOW | P1 |
| Local Whisper transcription | HIGH | MEDIUM | P1 |
| Clinical content filtering | HIGH | HIGH | P1 |
| SOAP note generation | HIGH | HIGH | P1 |
| Review & edit workflow (side-by-side) | HIGH | MEDIUM | P1 |
| Copy to clipboard | HIGH | LOW | P1 |
| Ephemeral data cleanup | HIGH | LOW | P1 |
| Session management | MEDIUM | LOW | P1 |
| CDT code suggestions | HIGH | MEDIUM | P2 |
| Appointment-type templates | MEDIUM | LOW | P2 |
| Dental terminology prompt | MEDIUM | LOW | P2 |
| Speaker diarization | MEDIUM | HIGH | P2 |
| Post-visit patient summary | LOW | LOW | P2 |
| Voice perio charting | HIGH | HIGH | P3 |
| Multi-provider support | LOW | MEDIUM | P3 |
| Referral letter generation | LOW | LOW | P3 |
| Treatment plan generation | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch -- without these, the product doesn't deliver its core value
- P2: Should have, add when core is proven -- these improve accuracy and workflow
- P3: Nice to have, future consideration -- high value but high complexity or out of scope

## Competitor Feature Analysis

| Feature | Freed AI | Overjet Voice (DentalBee) | VideaHealth Voice Notes | Denti.AI Scribe | Bola AI | Our Approach |
|---------|----------|---------------------------|-------------------------|-----------------|---------|--------------|
| **Deployment** | Cloud SaaS | Cloud SaaS | Cloud SaaS | Cloud SaaS | Cloud SaaS | **Local-only (differentiator)** |
| **Pricing** | ~$149/mo/provider | Enterprise pricing | Enterprise pricing | Per-provider pricing | Per-provider pricing | **Free after hardware** |
| **Recording** | Phone/tablet mic | Operatory mic (ambient) | Ambient + quick dictation | Standard mic, iOS app | Headset/lavalier/conference mic | Dedicated operatory mic (USB/BT conference or lavalier) |
| **Real-time transcript** | Yes (streaming) | Yes (ambient real-time) | Yes (Smart Ambient Mode) | Yes (real-time) | Yes (ambient) | No -- post-appointment generation (deliberate choice) |
| **Speaker diarization** | Basic (2 speakers) | Multi-speaker | Multi-speaker (Smart Ambient) | Multi-speaker (4+ roles) | Not confirmed | v1.x (enhancement, not launch) |
| **Note format** | SOAP, H&P, custom | Clinical notes, perio charts | Complaint/Findings/Assessment/Plan | SOAP or custom | Clinical notes | SOAP with dental sections |
| **CDT codes** | No (ICD-10 for medical) | Yes (via Overjet platform) | Not confirmed | Not confirmed | Claimed | v1.x (suggested, not auto-filed) |
| **Perio charting** | No | Yes (hands-free) | No | Not confirmed | Yes (Voice Perio) | v2+ (too complex for v1) |
| **PMS integration** | EHR push (browser-based) | Direct PMS write | PMS integration | Dentrix, Eaglesoft, Open Dental | Not confirmed | Copy-paste to Dentrix (v1) |
| **Review workflow** | Draft -> review -> sign -> push | Draft -> review -> save to PMS | One-click or batch review | Review -> edit -> save | Review -> edit | Side-by-side transcript + draft, inline edit |
| **Data retention** | No audio stored | 7-year encrypted audio storage | HIPAA-compliant storage | Not disclosed | Not disclosed | **Ephemeral -- deleted after finalization** |
| **Consent** | In-app consent | Not disclosed | Click-to-activate | Not disclosed | Not disclosed | Explicit consent gate before recording |
| **Dental-specific** | Medical-focused (60+ specialties) | Yes (dental-native) | Yes (dental-native) | Yes (dental-native) | Yes (dental-native) | Yes (dental-only) |
| **Language support** | English + some | English + Spanish | Not disclosed | English | English | English (v1) |
| **HIPAA** | SOC 2 Type II, HIPAA | HIPAA compliant | HIPAA compliant | HIPAA compliant | Not disclosed | Local-only = no BAA needed, no vendor data access |

### Competitive Positioning Summary

**Where competitors are strong and we cannot match:**
- Cloud competitors have massive training data (DeepScribe: 2M+ encounters, Freed: 27K+ medications). Our local LLM will produce lower quality notes initially.
- PMS direct integration (Denti.AI writes directly to Dentrix). Our copy-paste is more manual.
- Speaker diarization quality (cloud models with large training sets vs. local pyannote).
- Real-time note generation during the appointment (our approach is post-appointment).

**Where we win decisively:**
- **Privacy:** No patient data ever leaves the building. Zero cloud dependency. No BAA negotiations.
- **Cost:** $0/month vs. $149-399/month per provider. Runs on existing hardware.
- **Data control:** No vendor can access, sell, or train on patient conversations. No Sharp Healthcare class-action risk.
- **Simplicity:** No vendor contracts, no SaaS terms of service, no data retention policies to audit.

## Sources

### Competitor Products Analyzed
- [Freed AI - Ambient Clinical Documentation](https://www.getfreed.ai/resources/ambient-clinical-documentation) -- Cloud-based, 60+ specialties, EHR push
- [Overjet Voice (formerly DentalBee)](https://www.overjet.com/blog/overjet-brings-the-future-of-dental-documentation-to-every-operatory-with-general-availability-of-overjet-voice) -- Dental-specific, hands-free perio, 7-year audio storage
- [Overjet - DentalBee Acquisition](https://www.overjet.com/blog/overjet-adds-voice-powered-clinical-documentation-through-dentalbee-acquisition) -- December 2025 acquisition
- [VideaHealth Voice Notes](https://www.businesswire.com/news/home/20251029535866/en/VideaHealth-Launches-Voice-Notes-the-First-Ambient-AI-Scribe-Purpose-Built-for-Dentistry) -- Dental-native, 95% first-pass completeness
- [Denti.AI Scribe](https://www.denti.ai/scribe) -- Real-time, multi-speaker, Dentrix/Eaglesoft/Open Dental integration
- [Bola AI Scribe](https://bola.ai/solutions/ai-scribe/) -- Voice Perio, Voice Restorative, 10K+ dentists, 3M+ charts
- [DeepScribe](https://www.deepscribe.ai/) -- 98.8 KLAS score, specialty-tuned, HCC/CPT/ICD-10
- [Nuance DAX Copilot](https://www.nuance.com/healthcare/dragon-ai-clinical-solutions/dax-copilot.html) -- Microsoft-backed, Epic integration, style wizard
- [Nabla](https://www.nabla.com/) -- 150+ health systems, 35+ languages, $70M raised June 2025

### Dental Documentation Standards
- [Dental SOAP Notes Documentation Guide 2026](https://www.soapnoteai.com/soap-note-guides-and-example/dentistry/) -- SOAP structure, tooth numbering, perio documentation
- [ADA Templates, Smart Phrases and SOAP](https://www.ada.org/resources/practice/practice-management/templates-smart-phrases-and-soap) -- Official ADA guidance

### Microphone Hardware
- [Bola AI Recommended Microphones](https://bola.ai/microphones/) -- Headset, lavalier, and conference mic options for dental operatory
- [Philips SpeechMike Ambient](https://www.dictation.philips.com/us/philips-speechmike-ambient-wearable-ai-assistant-psm5000-series/) -- Clinical-grade wearable ambient mic

### Privacy, Consent, and Legal
- [Informed Consent for Ambient Documentation Using Generative AI](https://pmc.ncbi.nlm.nih.gov/articles/PMC12284739/) -- Consent models, patient preferences (96% want data handling disclosure)
- [HIPAA Compliance for Dental Offices 2026](https://hellopearl.com/blog/hipaa-compliance-for-dental-offices-in-2026-full-guide-pearl-ai) -- Dental-specific HIPAA guidance
- [AI Scribe Compliance Risks](https://www.healthlawattorneyblog.com/your-ai-scribe-is-listening-is-your-compliance-program/) -- Sharp Healthcare class action, two-party consent states
- [Florida Recording Laws](https://recordinglaw.com/party-two-party-consent-states/florida-recording-laws/) -- Two-party consent, felony penalties
- [AI Scribes Pose Liability Risks](https://www.mica-insurance.com/blog/posts/ai-scribes-pose-liability-risks/) -- Documentation accuracy, licensing board concerns

### Research and Evidence
- [Ambient AI Scribes Randomized Trial (NEJM AI)](https://ai.nejm.org/doi/abs/10.1056/AIoa2501000) -- 238 physicians, 72K encounters, 10% time reduction
- [Evaluating AI Scribe Documentation Quality](https://pmc.ncbi.nlm.nih.gov/articles/PMC12638734/) -- 19.5% transcript error transmission rate
- [Beyond Human Ears: Risks of AI Scribes](https://pmc.ncbi.nlm.nih.gov/articles/PMC12460601/) -- Hallucination, lack of context, follow-up setting errors
- [Ambient AI Scribe Policy Brief: Coding Arms Race](https://pmc.ncbi.nlm.nih.gov/articles/PMC12738533/) -- Overcoding risks from AI code suggestions

---
*Feature research for: Ambient clinical intelligence for dental practices*
*Researched: 2026-03-05*
