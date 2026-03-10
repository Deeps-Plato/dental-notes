# Phase 3: Review and Export - Research

**Researched:** 2026-03-10
**Domain:** HTMX/Jinja2 review UI, clipboard export, session persistence, file cleanup
**Confidence:** HIGH

## Summary

Phase 3 builds a review, editing, and export UI on top of the existing FastAPI + HTMX + Jinja2 stack established in Phases 1 and 2. The core work is: (1) a side-by-side split-panel review screen with fully editable transcript and SOAP note, (2) clipboard copy for Dentrix paste, (3) session persistence for batch note-writing workflows, and (4) transcript file deletion on finalization.

No new libraries are needed. The existing stack (FastAPI, HTMX 2.x, Jinja2, sse-starlette) plus standard browser APIs (`navigator.clipboard.writeText`) cover all requirements. Session persistence uses JSON files on disk -- no database required. The ExtractionResult model from Phase 2 provides the SOAP note, CDT codes, and clinical_discussion that populate the review screen.

**Primary recommendation:** Build the review screen as new Jinja2 templates with standard HTML `<textarea>` elements for editing (not contenteditable), use CSS Grid for the 50/50 split layout, and persist sessions as JSON files in a `sessions/` directory alongside the existing `transcripts/` directory.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Auto-extract SOAP note when session is stopped (no extra button click)
- Show loading state during GPU handoff (Whisper unload -> LLM inference)
- "Regenerate" button in review screen to re-run extraction if needed
- If dentist edits the transcript, show banner: "Transcript changed -- Regenerate note?" (dentist chooses)
- 50/50 side-by-side split: transcript on left, clinical note on right
- Both panels scroll independently
- No transcript highlighting or color-coding -- plain text with speaker labels
- Clinical Discussion appears inside the note panel as a section after CDT codes
- Note structure: Subjective (narrative+bullet hybrid), Objective (bullet-heavy), Assessment (clear-cut), Plan (clear-cut with narrative), CDT Codes, Clinical Discussion, Prescribed Medications (always at bottom)
- LLM auto-detects exam-only vs exam+procedure and adjusts format
- LLM auto-detects VA patients and generates per-tooth narrative section
- Everything is fully editable -- SOAP note AND transcript are editable text areas
- Type, dictate, cut/copy/paste, add, delete -- no restrictions, no read-only sections
- CDT codes fully editable -- add, remove, modify
- Clinical Discussion bullets fully editable
- Dictation (mic-to-text) available on any editable field at any stage using Whisper pipeline
- "Copy All" button copies the entire formatted note to clipboard (one-click, REV-03)
- Per-section copy icons for granular copying
- Clipboard format: plain text with section headers
- Sessions are saveable -- dentist can record multiple patients, save sessions, come back later
- Multiple saved sessions visible in a list with: timestamp + first line of transcript preview + status badge (Recorded / Extracted / Reviewed)
- Dentist picks which session to review/complete from the list
- "Finalize & Clear" button explicitly deletes transcript after dentist is done (AUD-02)
- Not auto-delete on copy -- two-step: copy first, then confirm finalization
- After finalization: confirmation message + clear path to "New Session" or return to session list

### Claude's Discretion
- Loading/progress UI during extraction
- Session list page layout and navigation
- Exact styling and CSS for the review screen
- How dictation mic button is presented on editable fields
- Session file format for saving/resuming incomplete notes
- Error handling for Ollama unavailable during extraction

### Deferred Ideas (OUT OF SCOPE)
- REV-04 (patient summary as patient-facing handout) -- future version
- Streaming LLM output (show SOAP note building in real-time) -- v2 enhancement
- Appointment-type templates (exam, restorative, hygiene, endo, extraction) -- v2 requirement ENH-01
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REV-01 | User can view full transcript side-by-side with the structured SOAP note draft | CSS Grid 50/50 layout, new review template, ExtractionResult model provides SOAP data |
| REV-02 | User can edit the AI-generated SOAP note before finalizing | Standard HTML `<textarea>` elements for each SOAP section, HTMX form submission for saving edits |
| REV-03 | User can copy the finalized note to clipboard in one click (Dentrix-ready format) | `navigator.clipboard.writeText()` -- works on localhost (secure context), plain text formatting function |
| REV-04 | A plain-language patient summary is generated alongside the clinical note | DEFERRED per user decision -- skip for v1 |
| AUD-02 | Transcript file is automatically deleted after the note is finalized | `Path.unlink(missing_ok=True)` for safe file deletion, two-step finalize flow |
</phase_requirements>

## Standard Stack

### Core (already installed -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.135.0 | Web framework, routes for review/session list/finalize | Already in use, HTMX partial returns |
| Jinja2 | >=3.1.0 | Server-side templates for review screen | Already in use, established patterns |
| HTMX | 2.0.4 (CDN) | Dynamic UI updates without JS framework | Already in use, OOB swaps established |
| sse-starlette | >=2.0.0 | SSE for extraction progress events | Already in use for transcript streaming |
| Pydantic | (via FastAPI) | Session data models, validation | Already in use for ExtractionResult |

### Supporting (already available)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | File deletion (AUD-02), session file management | Transcript cleanup, session JSON I/O |
| json | stdlib | Session persistence format | Save/load session state to disk |
| datetime | stdlib | Session timestamps | Session list sorting and display |
| uuid | stdlib | Session IDs | Unique session identifiers |
| shutil | stdlib | Potential directory cleanup | Only if needed for batch cleanup |

### Browser APIs (no libraries)
| API | Purpose | Compatibility |
|-----|---------|---------------|
| `navigator.clipboard.writeText()` | Copy note to clipboard | All modern browsers, works on localhost (secure context) |
| `window.isSecureContext` | Guard clipboard calls | Check before clipboard access |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON files for sessions | SQLite | SQLite adds dependency, overkill for <100 sessions/day, JSON files are simpler and match the project's file-based approach (transcripts/) |
| `<textarea>` for editing | `contenteditable` divs | contenteditable has browser inconsistencies with cursor position, paste behavior, and serialization; textarea is simpler and more reliable for plain text editing |
| CSS Grid layout | Flexbox | Both work; Grid is more explicit for 50/50 fixed columns with independent scroll |

**Installation:** No new packages needed. All dependencies already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
src/dental_notes/
├── session/
│   ├── manager.py           # EXISTING -- add save/load session state
│   ├── store.py             # NEW -- SessionStore: JSON file I/O for saved sessions
│   ├── speaker.py           # EXISTING
│   └── transcript_writer.py # EXISTING
├── clinical/
│   ├── extractor.py         # EXISTING -- used by review for extraction/re-extraction
│   ├── models.py            # EXISTING -- ExtractionResult, SoapNote, CdtCode
│   ├── ollama_service.py    # EXISTING
│   └── prompts.py           # EXISTING -- may need note format adjustments
├── ui/
│   ├── routes.py            # EXISTING -- add review, session list, finalize, copy routes
│   └── hotkey.py            # EXISTING
├── templates/
│   ├── index.html           # EXISTING -- becomes session list home page
│   ├── _session.html        # EXISTING
│   ├── _transcript.html     # EXISTING
│   ├── _transcript_oob.html # EXISTING
│   ├── review.html          # NEW -- side-by-side review screen
│   ├── _review_note.html    # NEW -- SOAP note panel partial (for HTMX swaps)
│   ├── _review_transcript.html  # NEW -- transcript panel partial
│   ├── sessions.html        # NEW -- session list page (or extend index.html)
│   └── _session_list.html   # NEW -- session list partial
├── static/
│   ├── style.css            # EXISTING -- extend with review screen styles
│   └── review.js            # NEW -- clipboard copy, dictation trigger, dirty tracking
├── config.py                # EXISTING -- add sessions_dir setting
└── main.py                  # EXISTING
```

### Pattern 1: Session Lifecycle Extension
**What:** Extend the IDLE -> RECORDING -> PAUSED -> STOPPING -> IDLE state machine with post-recording states.
**When to use:** After session stop, the session data needs to persist and be reviewable.

The session flow becomes:
```
IDLE -> RECORDING -> PAUSED -> RECORDING -> STOPPING -> IDLE
                                                          |
                                                     [auto-extract]
                                                          |
                                                     EXTRACTING -> REVIEW -> FINALIZED
```

However, rather than extending SessionManager's state machine (which manages audio), create a separate concept: **SavedSession**. After SessionManager.stop() returns, the transcript chunks and metadata are saved to a JSON file. The review screen operates on SavedSession objects, not on SessionManager.

```python
# Session store data model
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    RECORDED = "recorded"      # Transcript saved, not yet extracted
    EXTRACTED = "extracted"    # SOAP note generated
    REVIEWED = "reviewed"     # Dentist has reviewed/edited

class SavedSession(BaseModel):
    session_id: str = Field(description="UUID for this session")
    created_at: datetime
    updated_at: datetime
    status: SessionStatus = SessionStatus.RECORDED
    transcript_path: str = Field(description="Path to transcript .txt file")
    chunks: list[tuple[str, str]] = Field(description="(speaker, text) pairs")
    extraction_result: ExtractionResult | None = None
    edited_note: dict | None = None  # Dentist's edits override extraction_result
    transcript_dirty: bool = False  # True if transcript edited after extraction
```

### Pattern 2: Two-Step Stop + Extract Flow
**What:** When the dentist stops recording, automatically trigger extraction as a background task.
**When to use:** Every session stop.

```python
# In routes.py -- session stop triggers extraction
@router.post("/session/stop", response_class=HTMLResponse)
async def session_stop(request: Request):
    session_manager = _get_session_manager(request)
    transcript_path = session_manager.stop()
    chunks = session_manager.get_chunks()

    # Save session immediately (status: RECORDED)
    store = _get_session_store(request)
    session = store.create_session(chunks, transcript_path)

    # Redirect to review page (extraction happens there)
    # Return HTMX redirect to review screen
    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = f"/session/{session.session_id}/review"
    return response
```

### Pattern 3: Extraction as Loading State + SSE
**What:** Show a loading spinner/progress indicator while GPU handoff and LLM extraction run.
**When to use:** When the review page loads and extraction hasn't happened yet.

The extraction is CPU/GPU intensive (10-30 seconds). Use an SSE endpoint for progress:
```python
@router.get("/session/{session_id}/extract")
async def extract_session(request: Request, session_id: str):
    """SSE endpoint for extraction progress."""
    async def progress_generator():
        yield ServerSentEvent(data="Unloading Whisper model...", event="progress")
        # Run extraction in thread pool to not block asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: extractor.extract_with_gpu_handoff(transcript, whisper)
        )
        yield ServerSentEvent(data=json.dumps(result.model_dump()), event="complete")

    return EventSourceResponse(progress_generator())
```

Alternative (simpler): Use a regular POST that returns the full review page HTML after extraction completes. The HTMX request has a loading indicator shown via `hx-indicator`. This is simpler and avoids SSE complexity for a one-shot operation.

**Recommendation:** Use the simpler approach -- POST `/session/{id}/extract` with `hx-indicator` for loading state. The extraction takes 10-30 seconds; a spinner is sufficient. No need for granular SSE progress for a single operation.

### Pattern 4: Review Screen Layout
**What:** 50/50 CSS Grid split with independent scrolling panels.
**When to use:** The review page.

```html
<!-- review.html -->
<div class="review-container">
    <div class="panel panel-transcript">
        <div class="panel-header">
            <h2>Transcript</h2>
            <button class="btn-icon" onclick="copySection('transcript')">Copy</button>
        </div>
        <div class="panel-body">
            <textarea id="transcript-edit" name="transcript">{{ transcript_text }}</textarea>
        </div>
    </div>
    <div class="panel panel-note">
        <div class="panel-header">
            <h2>Clinical Note</h2>
            <button class="btn btn-copy" onclick="copyAll()">Copy All</button>
        </div>
        <div class="panel-body">
            <div class="note-section">
                <label>Subjective</label>
                <button class="btn-icon" onclick="copySection('subjective')">Copy</button>
                <textarea id="subjective" name="subjective">{{ soap.subjective }}</textarea>
            </div>
            <!-- ... more sections ... -->
        </div>
    </div>
</div>
```

```css
.review-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    height: calc(100vh - 120px); /* Full viewport minus header/footer */
}

.panel {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}

.panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
}
```

### Pattern 5: Session File Format (JSON)
**What:** Persist sessions as individual JSON files for save/resume workflow.
**When to use:** Every session save, load, update.

```
sessions/
├── a1b2c3d4.json    # One file per session
├── e5f6g7h8.json
└── ...
```

Each JSON file contains a `SavedSession` serialized via Pydantic's `model_dump_json()`. Session list reads all `.json` files from the directory, sorts by `created_at` descending.

### Pattern 6: Clipboard Copy Function
**What:** JavaScript function to format and copy note to clipboard.
**When to use:** "Copy All" button and per-section copy icons.

```javascript
async function copyAll() {
    const sections = ['subjective', 'objective', 'assessment', 'plan'];
    let text = '';

    for (const id of sections) {
        const el = document.getElementById(id);
        if (el && el.value.trim()) {
            text += id.charAt(0).toUpperCase() + id.slice(1) + ':\n';
            text += el.value.trim() + '\n\n';
        }
    }

    // CDT codes
    const cdtEl = document.getElementById('cdt-codes');
    if (cdtEl && cdtEl.value.trim()) {
        text += 'CDT Codes:\n' + cdtEl.value.trim() + '\n\n';
    }

    // Clinical Discussion
    const cdEl = document.getElementById('clinical-discussion');
    if (cdEl && cdEl.value.trim()) {
        text += 'Clinical Discussion:\n' + cdEl.value.trim() + '\n\n';
    }

    // Medications
    const medEl = document.getElementById('medications');
    if (medEl && medEl.value.trim()) {
        text += 'Prescribed Medications:\n' + medEl.value.trim() + '\n\n';
    }

    try {
        await navigator.clipboard.writeText(text.trim());
        showCopyFeedback('Copied to clipboard');
    } catch (err) {
        // Fallback for non-secure contexts (should not happen on localhost)
        fallbackCopy(text.trim());
    }
}
```

### Pattern 7: Transcript Dirty Tracking
**What:** Detect when dentist edits transcript after extraction and show regeneration banner.
**When to use:** In the review screen.

```javascript
// In review.js
const transcriptEl = document.getElementById('transcript-edit');
let originalTranscript = transcriptEl.value;

transcriptEl.addEventListener('input', function() {
    if (this.value !== originalTranscript) {
        document.getElementById('regen-banner').style.display = 'block';
    } else {
        document.getElementById('regen-banner').style.display = 'none';
    }
});
```

### Anti-Patterns to Avoid
- **Using contenteditable instead of textarea:** contenteditable has inconsistent paste behavior across browsers, cursor position issues, and HTML serialization complexity. For plain-text editing, `<textarea>` is simpler and more reliable.
- **Storing session state only in memory:** SessionManager resets on server restart. Sessions must be persisted to disk (JSON files) for the batch note-writing workflow.
- **Auto-deleting transcript on copy:** User explicitly decided against this. Two-step: copy first, then "Finalize & Clear" with confirmation.
- **Using a database for sessions:** SQLite adds complexity for a simple list of JSON documents. File-based storage is sufficient and matches the existing `transcripts/` pattern.
- **Blocking the event loop during extraction:** LLM inference takes 10-30 seconds. Must run in a thread pool executor (`run_in_executor`) or background thread.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Clipboard copy | Custom clipboard library or Flash-based copy | `navigator.clipboard.writeText()` | Browser-native, works on localhost, no dependencies |
| Session IDs | Custom ID generator | `uuid.uuid4()` | Standard, collision-free, no external dependency |
| JSON serialization for sessions | Custom serializer | Pydantic `model_dump_json()` / `model_validate_json()` | Already using Pydantic for ExtractionResult, consistent pattern |
| File deletion | Custom file cleanup with retries | `Path.unlink(missing_ok=True)` | stdlib, handles missing files gracefully, one line |
| CSS layout | Custom JavaScript panel resizer | CSS Grid `1fr 1fr` | Native CSS, no JS needed for fixed 50/50 split |
| Loading indicators | Custom spinner library | HTMX `hx-indicator` + CSS animation | Built into HTMX, matches existing patterns |
| Form data collection | Custom JavaScript form serializer | Standard HTML `<form>` + HTMX `hx-post` | HTMX automatically serializes form inputs |

**Key insight:** This phase is primarily UI/UX work. The heavy lifting (transcription, extraction) is done in Phases 1-2. Phase 3 connects the existing backend to new templates and adds persistence. No new algorithmic complexity.

## Common Pitfalls

### Pitfall 1: Clipboard API on non-localhost access
**What goes wrong:** If the dentist accesses the app via IP address (e.g., `http://192.168.1.5:8000`) instead of `http://localhost:8000`, `navigator.clipboard.writeText()` will fail silently because it requires a secure context.
**Why it happens:** The server binds to `0.0.0.0` for WSL access. Browser treats `localhost` and `127.0.0.1` as secure contexts, but NOT arbitrary IP addresses over HTTP.
**How to avoid:** Always use `http://localhost:8000` in the browser. Add a fallback using the deprecated `document.execCommand('copy')` with a hidden textarea for robustness. Check `window.isSecureContext` before calling clipboard API.
**Warning signs:** "Copy All" button does nothing, no error visible. Console shows `NotAllowedError`.

### Pitfall 2: Blocking asyncio event loop during extraction
**What goes wrong:** LLM extraction via Ollama takes 10-30 seconds. If called directly in an async route handler, it blocks all other requests (including the loading indicator).
**Why it happens:** `OllamaService.generate_structured()` uses synchronous `ollama.Client.chat()`. Calling it directly in an `async def` route blocks the event loop.
**How to avoid:** Use `asyncio.get_event_loop().run_in_executor(None, blocking_function)` to run extraction in a thread pool. Or use a non-async route (`def` instead of `async def`) which FastAPI automatically runs in a thread pool.
**Warning signs:** UI freezes during extraction, loading spinner doesn't animate, other browser tabs to the same server hang.

### Pitfall 3: Race condition on session file writes
**What goes wrong:** If the dentist rapidly clicks "Save" or "Regenerate", two concurrent requests could write to the same session JSON file simultaneously, corrupting it.
**Why it happens:** File I/O is not atomic by default.
**How to avoid:** Use atomic writes: write to a temp file, then `os.replace()` (atomic on same filesystem). Or use a simple lock per session_id. Given single-user, single-browser usage, this is low risk but worth protecting against.
**Warning signs:** Corrupted JSON file, session data loss.

### Pitfall 4: Textarea not auto-sizing for content
**What goes wrong:** Fixed-height textareas for SOAP note sections cut off content or show excessive whitespace.
**Why it happens:** Default textarea height doesn't match content length.
**How to avoid:** Auto-resize textareas based on content using `textarea.style.height = textarea.scrollHeight + 'px'` on input events and initial load.
**Warning signs:** Dentist has to scroll inside tiny textarea to see full Subjective section.

### Pitfall 5: Lost edits on page navigation
**What goes wrong:** Dentist edits SOAP note sections but navigates away (back to session list) without saving. Edits are lost.
**Why it happens:** No auto-save or "unsaved changes" warning.
**How to avoid:** Auto-save edits to the session JSON on every blur/input event (debounced), or show a `beforeunload` confirmation dialog when there are unsaved changes.
**Warning signs:** Dentist complains about lost work.

### Pitfall 6: GPU memory not freed after extraction
**What goes wrong:** After extraction, the LLM model stays loaded in GPU memory, preventing Whisper from loading for the next recording session.
**Why it happens:** `extract_with_gpu_handoff()` already handles this (unloads LLM, reloads Whisper in finally block). But if extraction is triggered from the review screen (Regenerate button), the code path must also do the GPU handoff.
**How to avoid:** All extraction calls must go through `extract_with_gpu_handoff()`. Never call `extract()` directly from a route.
**Warning signs:** Next recording session fails to start, or Whisper produces errors.

### Pitfall 7: Transcript file already deleted on finalize
**What goes wrong:** Dentist clicks "Finalize & Clear" twice, or the transcript file was already cleaned up.
**Why it happens:** Double-click, page refresh, or manual file deletion.
**How to avoid:** Use `Path.unlink(missing_ok=True)` which silently succeeds if file is already gone. Check file existence before displaying the finalize button.
**Warning signs:** 500 error on finalize (if not using `missing_ok=True`).

## Code Examples

Verified patterns from the existing codebase and official sources:

### Clipboard Copy with Fallback
```javascript
// Source: MDN Clipboard API docs + existing project patterns
async function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Clipboard API failed:', err);
        }
    }
    // Fallback: create temporary textarea
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        return true;
    } catch (err) {
        console.error('Fallback copy failed:', err);
        return false;
    } finally {
        document.body.removeChild(textarea);
    }
}
```

### Session Store (JSON file persistence)
```python
# Source: stdlib pathlib + pydantic patterns from existing codebase
import json
import uuid
from datetime import datetime
from pathlib import Path

class SessionStore:
    """File-based session persistence using JSON."""

    def __init__(self, sessions_dir: Path) -> None:
        self._dir = sessions_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        chunks: list[tuple[str, str]],
        transcript_path: Path,
    ) -> SavedSession:
        session = SavedSession(
            session_id=str(uuid.uuid4()),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            chunks=chunks,
            transcript_path=str(transcript_path),
        )
        self._write(session)
        return session

    def get_session(self, session_id: str) -> SavedSession | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        return SavedSession.model_validate_json(path.read_text())

    def list_sessions(self) -> list[SavedSession]:
        sessions = []
        for path in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                sessions.append(SavedSession.model_validate_json(path.read_text()))
            except Exception:
                continue
        return sessions

    def update_session(self, session: SavedSession) -> None:
        session.updated_at = datetime.now()
        self._write(session)

    def delete_session(self, session_id: str) -> None:
        path = self._dir / f"{session_id}.json"
        path.unlink(missing_ok=True)

    def _write(self, session: SavedSession) -> None:
        path = self._dir / f"{session.session_id}.json"
        # Atomic write: write temp file, then replace
        tmp = path.with_suffix('.tmp')
        tmp.write_text(session.model_dump_json(indent=2))
        tmp.replace(path)
```

### Transcript Cleanup (AUD-02)
```python
# Source: Python pathlib docs
from pathlib import Path

def finalize_session(session: SavedSession) -> None:
    """Delete transcript file and update session status."""
    transcript_path = Path(session.transcript_path)
    transcript_path.unlink(missing_ok=True)
    session.status = SessionStatus.FINALIZED
```

### HTMX Loading Indicator Pattern
```html
<!-- Source: HTMX docs hx-indicator -->
<button hx-post="/session/{{ session_id }}/extract"
        hx-target="#note-panel"
        hx-swap="innerHTML"
        hx-indicator="#extraction-spinner"
        class="btn btn-primary">
    Extract Note
</button>
<div id="extraction-spinner" class="htmx-indicator">
    <div class="spinner"></div>
    <p>Generating clinical note... (GPU processing)</p>
</div>
```

### Auto-Resize Textarea
```javascript
// Source: standard DOM pattern
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

// Apply to all textareas on load and input
document.querySelectorAll('textarea').forEach(function(ta) {
    autoResize(ta);
    ta.addEventListener('input', function() { autoResize(this); });
});
```

### Review Screen Form Submission
```python
# Source: existing routes.py patterns
@router.post("/session/{session_id}/save", response_class=HTMLResponse)
async def save_session_edits(
    request: Request,
    session_id: str,
    subjective: str = Form(""),
    objective: str = Form(""),
    assessment: str = Form(""),
    plan: str = Form(""),
    cdt_codes: str = Form(""),
    clinical_discussion: str = Form(""),
    medications: str = Form(""),
    transcript: str = Form(""),
):
    store = _get_session_store(request)
    session = store.get_session(session_id)
    if session is None:
        return HTMLResponse("Session not found", status_code=404)

    session.edited_note = {
        "subjective": subjective,
        "objective": objective,
        "assessment": assessment,
        "plan": plan,
        "cdt_codes": cdt_codes,
        "clinical_discussion": clinical_discussion,
        "medications": medications,
    }
    session.status = SessionStatus.REVIEWED
    store.update_session(session)
    # Return success feedback
    return HTMLResponse('<div class="save-success">Saved</div>')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `document.execCommand('copy')` | `navigator.clipboard.writeText()` | 2020 (Baseline) | Async, Promise-based, secure context required |
| Flexbox for two-column layout | CSS Grid `1fr 1fr` | 2017+ (widely supported) | More explicit, easier independent scroll |
| Server-rendered full page refreshes | HTMX partial swaps | Already established in project | No change needed, extend existing patterns |
| contenteditable for rich editing | `<textarea>` for plain text | N/A (always true for plain text) | Simpler, more reliable, better form integration |

**Deprecated/outdated:**
- `document.execCommand('copy')`: Deprecated but still works as fallback. Use `navigator.clipboard.writeText()` as primary.
- `hx-ws` for WebSocket HTMX communication: Not needed; SSE (`hx-ext="sse"`) is already working for streaming.

## Open Questions

1. **Dictation on editable fields (Whisper pipeline reuse)**
   - What we know: The user wants mic-to-text on any editable field. WhisperService is the existing transcription engine. The Whisper model must be loaded (not unloaded after extraction GPU handoff).
   - What's unclear: Should dictation create a new "mini session" (start capture -> transcribe -> insert text), or stream chunks into the textarea? How is the mic button UX presented per field?
   - Recommendation: Implement as a simple "hold to dictate" button per field. On press: start AudioCapture + WhisperService pipeline (ensure Whisper is loaded). On release: stop, insert transcribed text at cursor position in the textarea. Reuse existing AudioCapture + WhisperService + VadDetector. This is a smaller version of the recording pipeline.

2. **Note structure enrichment (medications, VA narrative)**
   - What we know: The LLM prompt in Phase 2 produces SoapNote with subjective, objective, assessment, plan, cdt_codes, clinical_discussion. The user wants additional sections: Prescribed Medications (always at bottom) and VA per-tooth narrative (conditionally).
   - What's unclear: These fields are not currently in the ExtractionResult Pydantic model. The extraction prompt needs to be updated to produce them.
   - Recommendation: Add `medications: list[str]` and `va_narrative: str | None` fields to SoapNote model. Update the EXTRACTION_SYSTEM_PROMPT to include instructions for these sections. The VA narrative is conditional (auto-detect from transcript), so `va_narrative` should be nullable.

3. **Session list as home screen vs current index.html**
   - What we know: The user wants the session list to be the home screen between appointments. Currently `index.html` shows mic selector + recording controls.
   - What's unclear: Should the recording controls move to a sub-page, or should the session list appear alongside them?
   - Recommendation: Make the session list the primary view at `/`. Recording controls (start/stop/pause) remain at the top as they are now, but below them show the session list. After recording stops, the session auto-saves and appears in the list. This keeps the single-page feel while adding session management.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.2.0 + pytest-asyncio >=0.23.0 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/ -x --tb=short` |
| Full suite command | `pytest tests/ --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REV-01 | Review page renders transcript and SOAP note side by side | unit (route) | `pytest tests/test_review_routes.py::test_review_page_renders_transcript_and_note -x` | Wave 0 |
| REV-02 | Editing SOAP note sections persists changes | unit (route) | `pytest tests/test_review_routes.py::test_save_edits_persists_to_session -x` | Wave 0 |
| REV-03 | Copy All formats note correctly for clipboard | unit (JS logic tested via Python formatter) | `pytest tests/test_note_formatter.py::test_format_note_for_clipboard -x` | Wave 0 |
| AUD-02 | Finalize deletes transcript file from disk | unit | `pytest tests/test_session_store.py::test_finalize_deletes_transcript -x` | Wave 0 |
| REV-01 | Side-by-side layout accessible | integration (route) | `pytest tests/test_review_routes.py::test_review_has_two_panels -x` | Wave 0 |
| AUD-02 | Finalize with already-deleted file succeeds | unit | `pytest tests/test_session_store.py::test_finalize_missing_file_succeeds -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x --tb=short`
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_session_store.py` -- covers session persistence (create, load, list, update, delete, finalize)
- [ ] `tests/test_review_routes.py` -- covers review page routes (render, save edits, extract, finalize, session list)
- [ ] `tests/test_note_formatter.py` -- covers clipboard text formatting (Copy All output, per-section copy)
- [ ] Update `tests/conftest.py` -- add FakeSessionStore, sample SavedSession fixtures

*(Existing test infrastructure (182+ tests, conftest.py fakes, httpx AsyncClient pattern) covers the testing foundation. New test files needed for Phase 3 features.)*

## Sources

### Primary (HIGH confidence)
- Existing codebase analysis: `src/dental_notes/` -- all source files read directly
- [MDN Clipboard API docs](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText) -- writeText() compatibility, secure context requirements
- [MDN Secure Contexts](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts) -- localhost treated as secure context (127.0.0.1 and localhost both work)
- [Python pathlib docs](https://docs.python.org/3/library/pathlib.html) -- Path.unlink(missing_ok=True) for safe file deletion
- [HTMX hx-preserve docs](https://htmx.org/attributes/hx-preserve/) -- limitations with input elements
- [HTMX hx-indicator docs](https://htmx.org/docs/) -- loading indicator pattern

### Secondary (MEDIUM confidence)
- [CSS-Tricks: Left Half and Right Half Layout](https://css-tricks.com/left-and-right/) -- CSS Grid 50/50 layout pattern verification
- [W3Schools: Two Column Layout](https://www.w3schools.com/howto/howto_css_two_columns.asp) -- CSS Grid column patterns
- [HTMX Click to Edit example](https://htmx.org/examples/click-to-edit/) -- editable content swap pattern
- [Can I Use: Clipboard writeText](https://caniuse.com/mdn-api_clipboard_writetext) -- browser support tables

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing libraries, patterns verified in codebase
- Architecture: HIGH -- extending established patterns (routes, templates, Pydantic models), no novel architecture
- Pitfalls: HIGH -- clipboard API behavior verified with MDN docs, asyncio blocking is well-documented, file ops are stdlib
- Session persistence: MEDIUM -- JSON file approach is straightforward but the specific schema (SavedSession model) will need validation during implementation

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable -- no fast-moving dependencies)
