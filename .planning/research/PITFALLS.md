# Pitfalls Research

**Domain:** Ambient dental clinical intelligence (local-first recording, transcription, SOAP note generation)
**Researched:** 2026-03-05
**Confidence:** HIGH (multiple peer-reviewed sources, real-world product data, regulatory statutes)

## Critical Pitfalls

### Pitfall 1: The "Demo Trap" -- Code That Doesn't Produce a Product

**What goes wrong:**
The previous attempt at this project is the canonical example: Flutter + FastAPI + cloud Whisper + Claude API produced 128 tests across 8 phases, but recording didn't transcribe and files weren't saved. The codebase looked complete -- tests passed, architecture was documented, phases were tracked -- but no actual dental note was ever generated from a real appointment. This pattern is endemic to healthcare AI projects, where 95% of organizations see no measurable ROI despite massive investment. Teams build scaffolding (auth, database schemas, cross-platform UI, API layers) instead of verifying the core value proposition works end-to-end.

**Why it happens:**
- Building infrastructure before proving the core pipeline works. The previous attempt built Flutter UI, FastAPI backend, SQLCipher encryption, biometric auth, and drift ORM before verifying that audio -> transcript -> note actually functioned.
- Treating the MVP as a premature enterprise product. Cross-platform Flutter (iOS/Android/Windows/macOS) when only Windows desktop is needed.
- Testing mocks instead of real hardware. Tests pass against mock audio data and mock API responses, giving false confidence. The real pipeline -- microphone -> WAV file -> Whisper -> structured text -- was never tested end-to-end.
- Scope creep from stakeholder pressure and "nice to have" features displacing core functionality.

**How to avoid:**
- **Phase 0 must produce a working recording that saves to disk.** Not a UI, not a database schema, not an API -- a WAV file from the microphone, saved, playable. Manual verification: "I can hear myself on this recording."
- **Phase 1 must produce a transcript from that recording.** Feed the saved WAV to faster-whisper, get text back, display it in a terminal. No UI framework needed.
- **Phase 2 must produce a structured note from that transcript.** Feed transcript text to local LLM, get SOAP note back, print it. No database needed.
- Each phase has a concrete, demonstrable artifact. If you cannot demonstrate the artifact to a non-technical person, the phase is not complete.
- No infrastructure (auth, database, encryption) until the core pipeline is proven. Infrastructure serves the pipeline, not the other way around.

**Warning signs:**
- Phase completion is defined by "code written" rather than "artifact produced"
- Tests pass but you cannot manually demonstrate the feature working
- Architecture diagrams exist but no output files exist
- More than 2 weeks pass without a real audio file being processed end-to-end
- UI work begins before the pipeline produces output in a terminal

**Phase to address:** Phase 0 (recording) and Phase 1 (transcription) must each produce verifiable artifacts before any other work begins. This is the single most important pitfall to prevent -- it killed the previous attempt entirely.

---

### Pitfall 2: Whisper Hallucinations -- Fabricated Clinical Content

**What goes wrong:**
Whisper generates text that was never spoken. In clinical contexts, this means fabricated medical details appearing in patient records. Research from Cornell and University of Washington found hallucinations in approximately 1.4% of transcriptions, with 40% of those hallucinations having potentially harmful consequences. Whisper has been documented inserting entire fabricated sentences, nonsensical phrases (e.g., "Thank you for watching!"), and even violent or racially charged content -- none of which was in the original audio. Hallucinations are most common during silence or low-speech segments, which are frequent in dental appointments (patient has mouth open, quiet pauses during examination).

**Why it happens:**
- Silence triggers the decoder to generate text from its training distribution rather than from audio input. Dental appointments have extended silences during procedures.
- Background noise (handpiece, suction) without clear speech creates ambiguous audio that the model "fills in" with plausible-sounding text.
- The model's autoregressive nature means one hallucinated token can cascade into a full hallucinated sentence.

**How to avoid:**
- **Use Silero VAD (Voice Activity Detection) to segment audio before transcription.** Only pass speech-containing segments to Whisper. The user already has Silero VAD experience from whisper-ptt.
- **Trim silence from the beginning and end of audio segments** before feeding to Whisper. Silence at segment boundaries is a primary hallucination trigger.
- **Use faster-whisper's `no_speech_threshold` parameter** (default 0.6) to suppress output during non-speech segments.
- **Use faster-whisper's `condition_on_previous_text=False`** to prevent hallucination cascading across segments.
- **Always retain the original audio until the dentist has reviewed and approved the note.** The audio is the ground truth for fact-checking.
- **Display confidence scores alongside transcript text** so the reviewer can spot low-confidence segments.

**Warning signs:**
- Transcript contains text that sounds like YouTube/podcast filler ("subscribe", "thank you for watching", "like and share")
- Transcript has content during periods when the patient's mouth was open (no speech was possible)
- Repeated phrases or loops in the transcript
- Transcript length seems longer than the actual conversation

**Phase to address:** Phase 1 (transcription). VAD preprocessing and hallucination mitigation must be built into the transcription pipeline from day one, not added later.

---

### Pitfall 3: Dental Equipment Noise Destroys Transcription Accuracy

**What goes wrong:**
High-speed dental handpieces produce 70-87 dB of noise. High-volume suction adds 89 dB. Combined, these exceed NIOSH recommended exposure limits of 85 dB and create a noise floor that overwhelms speech signals. Standard microphones placed at room distance capture more equipment noise than speech. Transcription accuracy drops severely -- research shows background noise increases clinically significant error rates (P<0.001). The result: garbled transcripts during procedures, which are precisely the moments when clinical documentation matters most.

**Why it happens:**
- Microphone placement at desk/counter distance (3-6 feet) captures room acoustics and equipment noise equally with speech.
- Dental operatory rooms are small, hard-surfaced (tile, laminate, metal), creating reverberant acoustics that amplify equipment noise.
- Unlike a quiet office dictation scenario, dental appointments have simultaneous speech and loud mechanical noise sources that overlap in frequency range.

**How to avoid:**
- **Use a directional or lapel microphone on the dentist, not a room microphone.** A lavalier mic clipped near the collar captures speech at high signal-to-noise ratio. The "inconspicuous" requirement is satisfied by small modern lapel mics.
- **Evaluate boundary/flat microphones designed for conference tables** as an alternative -- these have noise-rejection properties for desk placement.
- **Test audio quality with equipment running before building anything else.** Record 5 minutes of a real appointment with handpiece and suction running. If the recording is unintelligible to a human, no software will fix it.
- **Consider a two-microphone setup** -- one for the dentist (lapel), one for the patient (mounted near headrest). Speaker diarization becomes much simpler with physical separation.
- **Accept that during active high-speed handpiece use, transcription quality will be poor.** Design the workflow to handle gaps gracefully rather than expecting perfect transcription during drilling.

**Warning signs:**
- Audio recordings sound "muddy" or have persistent background hum/whine
- Transcription accuracy drops noticeably during procedures vs. during exam/consultation portions
- Word Error Rate exceeds 20% on test recordings with equipment running
- Whisper produces gibberish or silence during sections where speech occurred

**Phase to address:** Phase 0 (recording). Microphone selection and placement must be validated against real clinical noise before any transcription work begins. This is a hardware problem that software cannot solve.

---

### Pitfall 4: GPU VRAM Exhaustion When Running Whisper + LLM Simultaneously

**What goes wrong:**
The office machines have GTX 1050 (4 GB VRAM) minimum, with most being GTX 1070 Ti (8 GB VRAM). Running faster-whisper medium model needs ~2-3 GB VRAM. Running a local LLM (7B-8B Q4 quantized) needs ~5-6 GB VRAM. Running both simultaneously on a GTX 1070 Ti (8 GB) causes OOM errors. On a GTX 1050 (4 GB), even a single larger model may not fit. When models exceed VRAM, they fall back to CPU offloading, dropping inference speed from 40+ tokens/second to 1-3 tokens/second -- making the tool unusably slow.

**Why it happens:**
- GTX 10-series cards were designed for gaming, not ML inference. They lack the VRAM headroom of modern RTX cards.
- Developers test on their own hardware (often better than deployment targets) and discover the problem at deployment.
- VRAM requirements grow with context length -- an 8B model at 2K context uses ~0.3 GB KV cache, but at 32K context uses ~5 GB KV cache, potentially doubling total VRAM usage.
- Windows itself reserves 200-500 MB VRAM for desktop compositing, further reducing available memory.

**How to avoid:**
- **Run Whisper and LLM sequentially, not simultaneously.** Transcribe the full audio first, unload the Whisper model from VRAM, then load the LLM for note generation. This halves peak VRAM usage.
- **Use faster-whisper with int8 quantization** (`compute_type="int8"`). This reduces Whisper VRAM to ~1.5-2 GB for the medium model.
- **For the LLM, use Ollama with Q4_K_M quantization.** A Llama 3.1 8B Q4_K_M model uses ~5 GB VRAM.
- **Profile actual VRAM usage on the target GTX 1050 and GTX 1070 Ti hardware early.** Do not assume numbers from documentation -- measure them.
- **Have a CPU-only fallback path** for machines where GPU capacity is insufficient. Slower but functional.
- **Consider smaller Whisper models (small or base) for GTX 1050 machines.** The small model uses ~1 GB and is 6x faster than large-v2, with moderate accuracy tradeoff.

**Warning signs:**
- CUDA out-of-memory errors during testing
- Transcription takes longer than the appointment itself
- System becomes unresponsive during processing (GPU saturated, no VRAM for display)
- Dentrix or other applications on the same machine slow down during processing

**Phase to address:** Phase 0 (hardware audit) and Phase 1 (transcription). Must benchmark actual VRAM usage on the weakest target hardware before committing to model sizes.

---

### Pitfall 5: HIPAA Violations from Improper Audio Handling

**What goes wrong:**
Audio recordings of patient conversations are Protected Health Information (PHI). Storing them unencrypted, failing to delete them after use, transmitting them over a network, or allowing unauthorized access creates HIPAA violations. Civil penalties range from $100-$50,000 per violation. Criminal penalties reach $250,000 and 10 years imprisonment for willful violations. Even a "local-only" system can violate HIPAA if recordings persist on disk unencrypted, are accessible to other users on the machine, or are backed up to cloud storage (OneDrive, Google Drive, Dropbox) that syncs automatically.

**Why it happens:**
- Developers focus on the AI/ML pipeline and treat file management as an afterthought.
- Windows machines often have OneDrive or other cloud sync enabled by default -- saving a WAV file to Desktop or Documents silently uploads it to Microsoft's servers.
- "Temporary" files are not truly temporary unless explicitly deleted with secure erasure.
- Development/testing leaves behind sample recordings on disk that contain real patient data.
- Shared Windows login accounts in dental offices mean any staff member can access files.

**How to avoid:**
- **Write audio to a dedicated directory excluded from all cloud sync.** Verify OneDrive, Dropbox, Google Drive sync exclusions on each target machine.
- **Use Windows DPAPI or application-level encryption for audio files at rest.** Never store raw WAV files unencrypted.
- **Implement automatic deletion after the dentist finalizes the note.** The audio, transcript, and intermediate files must all be purged. Use secure deletion (overwrite, not just unlink).
- **Log all file creation and deletion events** for audit trail compliance.
- **Never write PHI to stdout, log files, or error reports.** A crash log containing patient transcript text is a HIPAA violation.
- **Test the deletion workflow explicitly:** create a recording, finalize a note, verify the recording file no longer exists on disk. Make this an automated test.

**Warning signs:**
- Audio files accumulate in a directory over time instead of being cleaned up
- OneDrive sync icon appears on the recording directory
- Crash logs or error messages contain transcript text
- No audit log of file lifecycle events
- Development test files contain real patient audio

**Phase to address:** Phase 0 (recording must use secure storage from day one) and every subsequent phase. HIPAA compliance is not a feature to add later -- it must be baked into file handling from the first line of code that touches audio.

---

### Pitfall 6: Florida Two-Party Consent Violations

**What goes wrong:**
Florida Statute 934.03 makes recording a private conversation without all-party consent a third-degree felony, punishable by up to 5 years in prison and $5,000 in fines. Civil liability under 934.10 adds minimum $1,000 per violation. In a dental office, "all parties" includes not just the patient and dentist, but also dental hygienists, assistants, specialists who walk in, and family members who accompany the patient. A posted sign is legally insufficient in Florida -- explicit consent is required. Recording begins before consent is obtained, or a new person enters the room during an active recording, and the recording becomes illegal.

**Why it happens:**
- Developers assume a posted sign ("This area is recorded") provides adequate notice. In Florida, it does not.
- The workflow does not account for multi-party dynamics: assistant enters mid-appointment, family member speaks up, specialist is called in.
- Recording starts automatically (ambient) without an explicit consent trigger.
- Consent is obtained verbally but not documented, making it unverifiable later.

**How to avoid:**
- **Require explicit, documented consent before recording begins.** A signed consent form, or at minimum a verbal consent captured on the recording itself ("Do you consent to this appointment being recorded for clinical documentation? [Yes]").
- **Add recording consent to the existing intake form workflow.** Patients already sign treatment consent forms -- add a recording consent checkbox with clear language about what is recorded, how it is used, and when it is deleted.
- **Build a consent-first workflow in the software.** Recording cannot start until a consent step is completed. No "always on" ambient recording.
- **Handle mid-appointment arrivals.** If a new person enters the room, the system should allow pausing the recording until consent is obtained from the new party.
- **Consult a Florida healthcare attorney** to draft the consent language. Template forms from the internet are not sufficient for the intersection of HIPAA + state wiretapping law + dental regulatory requirements.
- **Create a 50-state recording consent reference document** (Deep's stated requirement) to understand which states require one-party vs. two-party consent, for potential future expansion.

**Warning signs:**
- Recording starts without a consent step in the workflow
- No signed consent forms on file for recorded appointments
- Staff are unclear on when consent is required
- A recording contains voices from people who were not consented (family members, walk-in staff)
- No pause/resume capability for mid-appointment arrivals

**Phase to address:** Phase 0 (consent workflow must be designed before recording is implemented). Legal review should happen in parallel with early development, not after the product is built.

---

### Pitfall 7: Local LLM Note Quality Is Insufficient for Clinical Use

**What goes wrong:**
Local LLMs (7B-8B parameters, quantized to fit consumer GPUs) produce SOAP notes with three critical failure modes: (1) hallucinated clinical details -- inventing symptoms, medications, or findings not in the transcript; (2) omitted critical information -- missing key findings, allergies, or procedure details that were in the transcript; (3) inconsistent structure -- sometimes producing proper SOAP format, sometimes producing narrative text, sometimes mixing sections. Research shows a 1.47% hallucination rate and 3.45% omission rate even with well-tuned models. For dental-specific terminology (CDT codes, tooth numbering, periodontal measurements), smaller local models perform significantly worse than larger cloud models.

**Why it happens:**
- 7B-8B parameter models have limited medical knowledge compared to 70B+ models or cloud APIs.
- Q4 quantization further degrades knowledge retrieval for specialized vocabulary.
- Dental terminology is underrepresented in general training data compared to general medicine.
- Prompt engineering for structured output is brittle -- small changes in transcript format cause large changes in output quality.
- Clinicians found that when they worried about LLM quality, they preemptively wrote more detailed input that resembled finalized notes, eliminating time savings entirely.

**How to avoid:**
- **Treat the LLM output as a draft, never as a final note.** The UI must make this unmistakably clear -- the dentist reviews and edits before any note is considered complete.
- **Provide a structured prompt template with explicit SOAP sections, CDT code format, and tooth numbering conventions.** Do not rely on the model to infer structure.
- **Include a dental terminology reference in the system prompt** -- common CDT codes, tooth numbering (universal vs. Palmer), periodontal measurement formats.
- **Test with real dental transcripts before committing to a model.** Generate 20+ notes from real (or realistic) transcripts and have the dentist grade each one.
- **Consider a two-pass approach:** first pass extracts clinical entities (teeth, procedures, findings), second pass structures them into SOAP format. This is more reliable than single-pass generation.
- **Benchmark multiple local models** (Llama 3.1 8B, Mistral 7B, Phi-3, Qwen2.5) on dental-specific tasks before committing.
- **Have a fallback to a larger model** (if a machine has more VRAM) or CPU-offloaded larger model (slower but more accurate).

**Warning signs:**
- Generated notes mention procedures or findings not in the transcript
- Notes omit tooth numbers or procedure codes that were clearly discussed
- SOAP format is inconsistent between notes
- The dentist spends more time editing the draft than they would writing from scratch
- CDT codes are hallucinated (e.g., code doesn't exist or doesn't match the procedure)

**Phase to address:** Phase 2 (note generation). This phase needs extensive evaluation with real dental content before being considered complete. "It produces output" is not sufficient -- "the dentist would use this output" is the bar.

---

### Pitfall 8: Automation Bias -- Dentist Stops Reviewing AI-Generated Notes

**What goes wrong:**
After initial excitement and careful review, the dentist develops trust in the tool and begins rubber-stamping AI-generated notes without thorough review. This is "automation bias" -- the well-documented tendency of humans to over-trust automated systems. A hallucinated medication, omitted allergy, or fabricated finding gets signed into the patient record. In malpractice litigation, the signed note is the clinician's attestation that its contents are accurate. Research identifies this as a distinct failure mode of ambient AI scribes: "as heavy reliance on technology reduces cognitive load, physicians may be less likely to read every word of the draft note before finalizing it."

**Why it happens:**
- The tool produces good-enough output 95% of the time, training the user to expect correctness.
- Time pressure in a dental practice (5-10 patients/day) incentivizes fast approval.
- The side-by-side review interface makes it easy to glance and approve rather than carefully compare.
- No mechanism flags "high-risk" sections that need closer attention.

**How to avoid:**
- **Highlight low-confidence sections in the generated note.** Use color coding or bold to draw attention to parts the LLM was uncertain about.
- **Require explicit interaction with specific note sections** before allowing finalization. Not just a single "Approve" button -- require clicking into each SOAP section.
- **Show diff-style highlighting** of what the LLM added vs. what was in the raw transcript. Additions should be visually distinct.
- **Periodically audit finalized notes against original transcripts** (with patient consent for the review period) to catch systematic errors.
- **Never auto-approve or auto-finalize notes.** The dentist must take an explicit action for every note.

**Warning signs:**
- Time between note generation and finalization decreases over weeks (< 30 seconds = likely not reading)
- Finalized notes contain the same types of errors repeatedly
- Dentist reports the tool is "perfect" and doesn't need review (no AI system is perfect)
- No edits are made to any generated notes over a multi-week period

**Phase to address:** Phase 3 (review UI). The review workflow must be designed to resist automation bias from the start.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Storing audio as unencrypted WAV on disk | Simpler file handling | HIPAA violation risk, cloud sync exposure | Never -- encrypt from day one |
| Skipping VAD preprocessing | Faster pipeline setup | Whisper hallucinations on silent segments | Never -- VAD is proven and essential |
| Hardcoding model paths and sizes | Quick local development | Breaks on different machines with different VRAM | Only in Phase 0 prototyping, must be configurable by Phase 1 |
| Single monolithic Python script | Fast to write | Impossible to test components independently, hard to swap models | Only for initial proof-of-concept; refactor by Phase 2 |
| Using Whisper `tiny` or `base` model for speed | Fast transcription | Significantly worse medical term accuracy | Acceptable for GTX 1050 machines if tested and accuracy is tolerable |
| Skipping speaker diarization | Simpler pipeline | Cannot attribute statements to dentist vs. patient, LLM conflates speakers | Acceptable for MVP if the dentist reviews carefully; must add by Phase 3 |
| Processing audio in real-time during appointment | Immediate results | GPU contention with Dentrix, potential audio buffer overruns, complex state management | Never for v1 -- process after appointment ends |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Dentrix (copy-paste) | Building API integration or file import | Keep it simple: generate formatted text, one-click copy to clipboard. Dentrix API is out of scope and unnecessary |
| Windows audio devices | Assuming the default microphone is correct | Enumerate devices, let user select, persist the selection. Device names change across machines |
| CUDA / GPU drivers | Assuming CUDA works on all machines | Check CUDA availability at startup, fall back to CPU with a clear warning. Driver versions vary across office machines |
| OneDrive / cloud sync | Saving files to user directories | Use an app-specific directory outside sync-monitored paths (e.g., `C:\ProgramData\DentalNotes\`) |
| Windows User Account Control | Running with admin privileges | Run as standard user. Only request elevation if absolutely needed (driver install) |
| Ollama / llama.cpp | Assuming GPU offloading works out of the box | Test GPU layer offloading on each target hardware profile. Some GTX 10-series have CUDA compute capability issues with certain operations |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Processing audio in real-time during appointment | Dentrix slows down, audio glitches, GPU at 100% | Process after appointment, not during | Immediately -- real-time is not needed and creates problems |
| Loading full appointment audio into memory | OOM for longer appointments (30 min @ 16kHz = ~57 MB PCM) | Stream audio in chunks, process in segments | Appointments over ~15 minutes on low-RAM machines |
| LLM context window overflow | Truncated notes, missing information from end of appointment | Chunk long transcripts, summarize incrementally, or use sliding window | Transcripts exceeding ~4000 tokens (~3000 words / ~20 min conversation) |
| No model caching between appointments | 10-30 second cold-start loading Whisper + LLM for each appointment | Keep models loaded between appointments (background service) | Every appointment -- cold loading is the #1 latency complaint |
| Synchronous UI blocking during processing | Frozen/unresponsive interface during transcription/generation | Background processing with progress indicator | Always -- transcription of 20 min audio takes 1-5 min on GTX 1070 Ti |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Writing PHI to log files | HIPAA violation; log files persist, get backed up, get included in bug reports | Never log transcript content. Log events only (timestamps, durations, error codes) |
| Audio files in user-accessible directories | Any user on the shared Windows machine can access recordings | Store in app-specific encrypted directory with per-session keys |
| Crash dumps containing transcript state | Python tracebacks can include variable values = patient data | Install custom exception handler that sanitizes PHI before logging |
| Network requests during processing | Even a health check or telemetry ping during audio processing could leak metadata | Air-gap the processing pipeline. No network calls during recording/transcription/generation |
| Clipboard containing PHI after paste | Transcript text remains in clipboard after copy-paste to Dentrix | Clear clipboard after a configurable timeout (30 seconds) or after Dentrix paste is detected |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Requiring the dentist to start/stop recording manually | Forgotten recordings, missed appointments, interrupted workflow | One-click start at appointment begin, auto-stop on silence timeout or manual stop |
| Showing raw transcript before AI processing | Dentist reads messy, disorganized transcript and loses confidence in the tool | Show structured note first, with option to expand full transcript for verification |
| Making the review process too complex | Too many clicks = tool gets abandoned | Side-by-side view (transcript | note), single approve button per section, one final "Copy to Dentrix" action |
| Visible recording indicator that patients notice | Patients feel surveilled, refuse consent, create awkward dynamics | Inconspicuous recording indicator on the workstation screen, not a flashing light or visible microphone |
| No feedback when processing is happening | Dentist thinks the tool crashed or frozen | Clear progress indicator: "Recording saved... Transcribing (2 of 5 segments)... Generating note..." |
| Processing takes too long between appointments | Dentist falls behind schedule waiting for notes | Target < 2 minutes total processing for a 15-minute appointment. If hardware can't meet this, queue processing and alert when ready |

## "Looks Done But Isn't" Checklist

- [ ] **Recording:** "Microphone works" is not sufficient -- verify audio quality is adequate for transcription by playing back and listening to a test recording with dental equipment running
- [ ] **Transcription:** "Whisper produces text" is not sufficient -- verify the text matches what was actually said by comparing against a known script
- [ ] **Note generation:** "LLM produces a SOAP note" is not sufficient -- verify the note contains no hallucinated content and no omitted critical findings
- [ ] **File cleanup:** "Files are deleted" is not sufficient -- verify files are deleted from disk (not just in-memory references), and verify cloud sync did not copy them
- [ ] **Consent workflow:** "Patient signs a form" is not sufficient -- verify the form language is legally adequate for Florida two-party consent AND HIPAA
- [ ] **GPU compatibility:** "Works on my machine" is not sufficient -- verify on the weakest target hardware (GTX 1050, 4 GB VRAM) under realistic load
- [ ] **End-to-end pipeline:** "Each component works in isolation" is not sufficient -- verify the full pipeline (record -> transcribe -> generate -> review -> copy -> cleanup) works without manual intervention between steps
- [ ] **Error recovery:** "Happy path works" is not sufficient -- verify what happens when recording fails mid-appointment, Whisper crashes, LLM produces garbage, or the machine runs out of VRAM
- [ ] **Multi-appointment:** "Works for one appointment" is not sufficient -- verify the tool handles 5-10 appointments in sequence without accumulating state, leaking memory, or filling disk

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Demo trap (no working pipeline) | HIGH | Start over with pipeline-first approach. Discard previous architecture. Build recording -> transcription -> note in sequential phases with artifact verification |
| Whisper hallucinations in production | MEDIUM | Add VAD preprocessing, enable `condition_on_previous_text=False`, tune `no_speech_threshold`. Requires reprocessing affected recordings if they still exist |
| Audio quality issues | HIGH | Hardware change required (different microphone). Software cannot compensate for inadequate signal-to-noise ratio. Must re-evaluate microphone placement and type |
| VRAM exhaustion on target hardware | MEDIUM | Switch to sequential model loading (Whisper then LLM), use smaller models, or enable CPU offloading. May require downgrading model quality |
| HIPAA violation (files not deleted) | HIGH | Immediate incident response: identify all exposed files, determine if cloud-synced, document the breach. Legal notification may be required. Implement secure deletion and audit logging going forward |
| Florida consent violation | CRITICAL | Legal consultation immediately. Cannot be fixed retroactively. All recordings made without proper consent may need to be destroyed. Potential criminal liability |
| LLM note quality too low | MEDIUM | Iterate on prompts, try different models, consider hybrid approach (local extraction + structured template). If no local model is adequate, reconsider architecture (dedicated medical model, or limited cloud use with BAA) |
| Automation bias (errors in signed notes) | HIGH | Retrospective audit of all signed notes against original transcripts. Implement UI changes to force more careful review. Cannot unsign notes already in patient records |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Demo trap | Phase 0-2 | Each phase produces a demonstrable artifact that a non-technical person can verify |
| Whisper hallucinations | Phase 1 (transcription) | Run 20+ test recordings through pipeline, manually verify zero fabricated content |
| Dental noise interference | Phase 0 (recording/hardware) | Test recordings with handpiece and suction running are intelligible to a human listener |
| GPU VRAM exhaustion | Phase 0 (hardware audit) | Benchmark VRAM usage on GTX 1050 (4 GB) with target models; document supported configurations |
| HIPAA file handling | Phase 0 (recording) | Automated test: create recording, finalize note, verify recording file does not exist on disk or in any sync directory |
| Florida consent | Phase 0 (pre-development) | Signed consent form template reviewed by Florida healthcare attorney |
| LLM note quality | Phase 2 (note generation) | Dentist grades 20+ generated notes; >80% require only minor edits (not rewrites) |
| Automation bias | Phase 3 (review UI) | UI requires explicit interaction with each SOAP section; analytics track review time per note |

## Sources

- [Navina Research: Ambient-Only Clinical Documentation Misses Critical Patient Context](https://www.navina.ai/news/new-research-finds-ambient-only-clinical-documentation-misses-critical-patient-context)
- [npj Digital Medicine: Beyond Human Ears -- Risks of AI Scribes](https://www.nature.com/articles/s41746-025-01895-6)
- [The Ambient Liability Trap: Why 2026 is the Year of Human-in-the-Loop](https://medium.com/@ryanshrott/the-ambient-liability-trap-why-2026-is-the-year-of-the-human-in-the-loop-36f7ceb9abce)
- [AMA Journal of Ethics: Ambient Listening and Transcription Technologies](https://journalofethics.ama-assn.org/article/how-should-we-think-about-ambient-listening-and-transcription-technologies-influences-ehr/2025-11)
- [McAfee & Taft: Risks of Virtual Scribes and Ambient Listening](https://www.mcafeetaft.com/healthcarelinc-qa-the-risks-of-using-virtual-scribes-and-ambient-listening-for-documentation/)
- [PBS News: AI Transcription Tool That Hallucinates Medical Interactions](https://www.pbs.org/newshour/show/what-to-know-about-an-ai-transcription-tool-that-hallucinates-medical-interactions)
- [Healthcare Brew: OpenAI Whisper Makes Up Words Patients Never Said](https://www.healthcare-brew.com/stories/2024/11/18/openai-transcription-tool-whisper-hallucinations)
- [Fortune: OpenAI Whisper Hallucination Rate](https://fortune.com/2024/10/26/openai-transcription-tool-whisper-hallucination-rate-ai-tools-hospitals-patients-doctors/)
- [Science/AAAS: AI Transcription Tools Hallucinate Too](https://www.science.org/content/article/ai-transcription-tools-hallucinate-too)
- [npj Digital Medicine: Framework to Assess Clinical Safety and Hallucination Rates of LLMs](https://www.nature.com/articles/s41746-025-01670-7)
- [ACM WSDM: SpecialtyScribe -- SOAP Note Scribing for Medical Specialties](https://dl.acm.org/doi/10.1145/3701551.3706131)
- [Transdyne: 12 Common Ambient AI Scribe Failures](https://transdyne.com/ambient-ai-scribes-failure-modes-human-ai-hybrid/)
- [HCI Innovation Group: Ambient Scribe Physician Adoption Uneven](https://www.hcinnovationgroup.com/home/article/55283221/ambient-scribe-physician-adoption-uneven-as-use-cases-evolve)
- [DeepScribe: Why Generic Ambient AI Falls Short for Specialties](https://www.deepscribe.ai/resources/ai-for-specialty-care-4-reasons-why-generic-ambient-ai-solutions-fall-short)
- [PMC: Dental Clinic Noise Levels](https://pmc.ncbi.nlm.nih.gov/articles/PMC9776681/)
- [MDPI: Evaluation of Noise Levels in University Dental Clinic](https://www.mdpi.com/2076-3417/13/19/10869)
- [PMC: Sound Levels in Conservative Dentistry](https://pmc.ncbi.nlm.nih.gov/articles/PMC3659855/)
- [GitHub: Whisper Memory Requirements Discussion](https://github.com/openai/whisper/discussions/5)
- [GitHub: Whisper GTX 1050 Ti Discussion](https://github.com/openai/whisper/discussions/47)
- [GitHub: Whisper Performance Benchmarks](https://github.com/openai/whisper/discussions/918)
- [LocalLLM.in: Ollama VRAM Requirements 2026 Guide](https://localllm.in/blog/ollama-vram-requirements-for-local-llms)
- [Paubox: HIPAA Regulations for Audio Recording](https://www.paubox.com/blog/understanding-hipaa-regulations-for-audio-recording)
- [iFax: HIPAA Violation Audio Recording](https://www.hipaaexams.com/blog/doctors-record-patients)
- [Florida Statute 934.03: Security of Communications](https://recordinglaw.com/party-two-party-consent-states/florida-recording-laws/)
- [CDA: Hidden Dangers of Audio Recording in the Dental Office](https://www.cda.org/newsroom/2023/hidden-dangers-ethical-and-legal-risks-of-audio-and-video-recording-in-the-dental-office/)
- [Boston Technology: Why Healthcare AI PoCs Fail the Production Test](https://www.boston-technology.com/blog/why-healthcare-ai-pocs-fail-the-production-test)
- [Becker's: Why 95% of Healthcare AI Projects Fail](https://www.beckershospitalreview.com/healthcare-information-technology/why-95-of-healthcare-ai-projects-fail-and-how-to-change-this/)
- [Dental Audio Notes (DAN): Real Dental Recording Product](https://dentalaudionotes.com/)
- [King's College London: Transcription Accuracy of ASR for Clinical Orthodontics](https://kclpure.kcl.ac.uk/portal/en/publications/transcription-accuracy-of-automatic-speech-recognition-for-clinic/)
- [arxiv: Calm-Whisper -- Reduce Whisper Hallucination on Non-Speech](https://arxiv.org/html/2505.12969v1)
- [GitHub: faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Whisper Prompt Engineering for Custom Vocabulary](https://medium.com/axinc-ai/prompt-engineering-in-whisper-6bb18003562d)
- [Sotto Blog: Improve Whisper Accuracy with Initial Prompts](https://sotto.to/blog/improve-whisper-accuracy-prompts)

---
*Pitfalls research for: Ambient dental clinical intelligence*
*Researched: 2026-03-05*
