/**
 * Review page JavaScript: clipboard copy, dirty tracking, auto-resize, dictation.
 *
 * Handles:
 * - Copy All: fetches server-formatted text via /api/session/{id}/note-text
 * - Per-section copy: reads textarea value and copies with section header
 * - Transcript dirty tracking: shows regen banner when transcript changes
 * - Auto-resize textareas: adjusts height to content on load and input
 * - Dictation: mic-to-text via browser MediaRecorder -> POST /dictate
 */

// --- Clipboard helpers ---

/**
 * Copy text to clipboard with fallback for non-secure contexts.
 * Uses navigator.clipboard.writeText when available (localhost is secure),
 * falls back to hidden textarea + execCommand for robustness.
 */
function copyToClipboard(text) {
    if (window.isSecureContext && navigator.clipboard) {
        return navigator.clipboard.writeText(text).then(function () {
            return true;
        }).catch(function () {
            return fallbackCopy(text);
        });
    }
    return Promise.resolve(fallbackCopy(text));
}

function fallbackCopy(text) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand("copy");
        return true;
    } catch (e) {
        return false;
    } finally {
        document.body.removeChild(textarea);
    }
}

/**
 * Show brief "Copied!" feedback near a button element.
 * Auto-dismisses after 2 seconds.
 */
function showCopyFeedback(buttonElement, message) {
    var feedback = document.createElement("span");
    feedback.className = "copy-feedback";
    feedback.textContent = message || "Copied!";
    buttonElement.parentNode.insertBefore(feedback, buttonElement.nextSibling);
    setTimeout(function () {
        if (feedback.parentNode) {
            feedback.parentNode.removeChild(feedback);
        }
    }, 2000);
}

// --- Copy functions ---

/**
 * Copy entire formatted note via server-side formatting.
 * Fetches from /api/session/{sessionId}/note-text for consistent output.
 */
function copyAll(sessionId) {
    var btn = event.currentTarget || event.target;
    fetch("/api/session/" + sessionId + "/note-text")
        .then(function (response) {
            return response.text();
        })
        .then(function (text) {
            return copyToClipboard(text);
        })
        .then(function () {
            showCopyFeedback(btn, "Copied!");
        })
        .catch(function () {
            showCopyFeedback(btn, "Copy failed");
        });
}

/**
 * Copy a single SOAP section with its header.
 * Reads directly from the textarea to capture user edits.
 */
function copySection(sectionName) {
    var textarea = document.getElementById(sectionName);
    if (!textarea) return;

    var displayName = sectionName.replace(/_/g, " ");
    displayName = displayName.charAt(0).toUpperCase() + displayName.slice(1);

    var text = displayName + ":\n" + textarea.value;
    var btn = textarea.closest(".note-section").querySelector(".btn-icon");

    copyToClipboard(text).then(function () {
        if (btn) showCopyFeedback(btn, "Copied!");
    });
}

/**
 * Copy transcript text to clipboard.
 */
function copyTranscript(sessionId) {
    var textarea = document.getElementById("transcript-edit");
    if (!textarea) return;

    var btn = event.currentTarget || event.target;
    copyToClipboard(textarea.value).then(function () {
        showCopyFeedback(btn, "Copied!");
    });
}

// --- Dirty tracking ---

var originalTranscript = "";

/**
 * Track changes to transcript textarea.
 * Shows the regen banner when transcript differs from original.
 */
function trackTranscriptChange(textarea) {
    var banner = document.getElementById("regen-banner");
    if (!banner) return;

    if (textarea.value !== originalTranscript) {
        banner.style.display = "flex";
    } else {
        banner.style.display = "none";
    }
}

// --- Auto-resize ---

/**
 * Auto-resize a textarea to fit its content.
 * Sets height to auto first, then to scrollHeight.
 */
function autoResize(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
}

/**
 * Auto-resize all textareas on the page.
 */
function autoResizeAll() {
    var textareas = document.querySelectorAll("textarea");
    textareas.forEach(function (textarea) {
        autoResize(textarea);
    });
}

// --- Dictation (mic-to-text via Whisper) ---

/**
 * Dictation state: tracks active recording per textarea.
 * Only one dictation can be active at a time.
 */
var activeDictation = {
    targetId: null,
    mediaRecorder: null,
    audioChunks: [],
    stream: null
};

/**
 * Toggle dictation for a textarea: start recording if idle, stop if active.
 *
 * Uses the browser MediaRecorder API to capture mic audio. On stop,
 * converts the recorded audio to PCM 16-bit 16kHz mono, sends to
 * POST /dictate, and inserts the returned text at the cursor position
 * in the target textarea.
 */
function toggleDictation(textareaId) {
    if (activeDictation.targetId === textareaId) {
        stopDictation();
    } else {
        if (activeDictation.targetId !== null) {
            stopDictation();
        }
        startDictation(textareaId);
    }
}

/**
 * Start recording audio for dictation into the specified textarea.
 */
function startDictation(textareaId) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Microphone access not available in this browser.");
        return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function (stream) {
            activeDictation.stream = stream;
            activeDictation.targetId = textareaId;
            activeDictation.audioChunks = [];

            var mediaRecorder = new MediaRecorder(stream, {
                mimeType: getRecorderMimeType()
            });
            activeDictation.mediaRecorder = mediaRecorder;

            mediaRecorder.ondataavailable = function (e) {
                if (e.data.size > 0) {
                    activeDictation.audioChunks.push(e.data);
                }
            };

            mediaRecorder.onstop = function () {
                processDictationAudio(textareaId);
            };

            mediaRecorder.start();
            updateDictationButton(textareaId, true);
        })
        .catch(function (err) {
            alert("Microphone permission denied: " + err.message);
        });
}

/**
 * Stop the active dictation recording.
 */
function stopDictation() {
    if (activeDictation.mediaRecorder &&
        activeDictation.mediaRecorder.state !== "inactive") {
        activeDictation.mediaRecorder.stop();
    }
    if (activeDictation.stream) {
        activeDictation.stream.getTracks().forEach(function (track) {
            track.stop();
        });
        activeDictation.stream = null;
    }
    var targetId = activeDictation.targetId;
    activeDictation.targetId = null;
    activeDictation.mediaRecorder = null;
    if (targetId) {
        updateDictationButton(targetId, false);
    }
}

/**
 * Get the best available MIME type for MediaRecorder.
 */
function getRecorderMimeType() {
    var types = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/mp4"
    ];
    for (var i = 0; i < types.length; i++) {
        if (MediaRecorder.isTypeSupported(types[i])) {
            return types[i];
        }
    }
    return "";
}

/**
 * Process recorded audio: decode to PCM, send to /dictate, insert text.
 */
function processDictationAudio(textareaId) {
    if (activeDictation.audioChunks.length === 0) return;

    var blob = new Blob(activeDictation.audioChunks);
    activeDictation.audioChunks = [];

    // Show processing state on button
    setDictationProcessing(textareaId, true);

    // Decode audio blob to raw PCM using AudioContext
    var reader = new FileReader();
    reader.onload = function () {
        var arrayBuffer = reader.result;
        var audioContext = new (window.AudioContext ||
            window.webkitAudioContext)();

        audioContext.decodeAudioData(arrayBuffer)
            .then(function (audioBuffer) {
                // Resample to 16kHz mono PCM 16-bit
                var pcmBytes = audioBufToPcm16k(audioBuffer);

                // Send to /dictate endpoint
                return fetch("/dictate", {
                    method: "POST",
                    headers: { "Content-Type": "application/octet-stream" },
                    body: pcmBytes
                });
            })
            .then(function (response) {
                if (response.status === 503) {
                    alert("Whisper model busy (GPU in use for extraction). "
                        + "Try again after extraction completes.");
                    return null;
                }
                return response.json();
            })
            .then(function (data) {
                if (data && data.text) {
                    insertTextAtCursor(textareaId, data.text);
                }
                setDictationProcessing(textareaId, false);
                audioContext.close();
            })
            .catch(function (err) {
                setDictationProcessing(textareaId, false);
                audioContext.close();
                alert("Dictation failed: " + err.message);
            });
    };
    reader.readAsArrayBuffer(blob);
}

/**
 * Convert AudioBuffer to 16kHz mono PCM 16-bit little-endian bytes.
 *
 * Downsamples from the AudioBuffer's sample rate to 16kHz and
 * converts float32 samples to signed 16-bit integers.
 */
function audioBufToPcm16k(audioBuffer) {
    var TARGET_RATE = 16000;
    var sourceSampleRate = audioBuffer.sampleRate;

    // Get mono channel (use first channel)
    var inputData = audioBuffer.getChannelData(0);

    // Resample to 16kHz using linear interpolation
    var ratio = sourceSampleRate / TARGET_RATE;
    var outputLength = Math.floor(inputData.length / ratio);
    var output = new Int16Array(outputLength);

    for (var i = 0; i < outputLength; i++) {
        var srcIndex = i * ratio;
        var srcFloor = Math.floor(srcIndex);
        var srcCeil = Math.min(srcFloor + 1, inputData.length - 1);
        var frac = srcIndex - srcFloor;

        // Linear interpolation
        var sample = inputData[srcFloor] * (1 - frac) +
            inputData[srcCeil] * frac;

        // Clamp to [-1, 1] and convert to 16-bit signed int
        sample = Math.max(-1, Math.min(1, sample));
        output[i] = Math.round(sample * 32767);
    }

    return new Uint8Array(output.buffer);
}

/**
 * Insert text at the cursor position in a textarea.
 * If no cursor position, appends to the end with a space separator.
 */
function insertTextAtCursor(textareaId, text) {
    var textarea = document.getElementById(textareaId);
    if (!textarea) return;

    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var before = textarea.value.substring(0, start);
    var after = textarea.value.substring(end);

    // Add space separator if needed
    var separator = "";
    if (before.length > 0 && !before.endsWith(" ") && !before.endsWith("\n")) {
        separator = " ";
    }

    textarea.value = before + separator + text + after;
    textarea.selectionStart = start + separator.length + text.length;
    textarea.selectionEnd = textarea.selectionStart;

    // Trigger auto-resize and dirty tracking
    autoResize(textarea);
    if (textareaId === "transcript-edit") {
        trackTranscriptChange(textarea);
    }

    textarea.focus();
}

/**
 * Update the dictation button visual state (recording vs idle).
 */
function updateDictationButton(textareaId, isRecording) {
    // Find the mic button for this textarea
    var textarea = document.getElementById(textareaId);
    if (!textarea) return;

    var section = textarea.closest(".note-section") ||
        textarea.closest(".transcript-panel");
    if (!section) return;

    var btn = section.querySelector(".btn-dictate");
    if (!btn) return;

    if (isRecording) {
        btn.classList.add("dictating");
        btn.title = "Stop dictation";
    } else {
        btn.classList.remove("dictating");
        btn.title = "Dictate into section";
    }
}

/**
 * Show/hide processing indicator on dictation button.
 */
function setDictationProcessing(textareaId, isProcessing) {
    var textarea = document.getElementById(textareaId);
    if (!textarea) return;

    var section = textarea.closest(".note-section") ||
        textarea.closest(".transcript-panel");
    if (!section) return;

    var btn = section.querySelector(".btn-dictate");
    if (!btn) return;

    if (isProcessing) {
        btn.classList.add("dictate-processing");
        btn.title = "Processing...";
    } else {
        btn.classList.remove("dictate-processing");
        btn.title = "Dictate into section";
    }
}

// --- Tab switching ---

/**
 * Switch active tab in the right panel.
 * Toggles .active class on tab buttons and corresponding .tab-content divs.
 * Stores active tab in data-active-tab attribute for restoration after HTMX swaps.
 */
function switchTab(tabId) {
    var panel = document.querySelector(".note-panel");
    if (!panel) return;

    // Update buttons
    var buttons = panel.querySelectorAll(".tab-btn");
    buttons.forEach(function (btn) {
        if (btn.getAttribute("data-tab") === tabId) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    // Update content
    var contents = panel.querySelectorAll(".tab-content");
    contents.forEach(function (content) {
        if (content.id === tabId) {
            content.classList.add("active");
        } else {
            content.classList.remove("active");
        }
    });

    // Store active tab for restoration after HTMX swaps
    panel.setAttribute("data-active-tab", tabId);
}

/**
 * Restore active tab from data-active-tab attribute.
 * Called after HTMX swaps to preserve tab state.
 */
function restoreActiveTab() {
    var panel = document.querySelector(".note-panel");
    if (!panel) return;

    var activeTab = panel.getAttribute("data-active-tab");
    if (activeTab) {
        switchTab(activeTab);
    }
}

// --- Copy summary ---

/**
 * Copy patient summary to clipboard as formatted plain text.
 */
function copySummary() {
    var whatWeDid = document.getElementById("what_we_did");
    var whatsNext = document.getElementById("whats_next");
    var homeCare = document.getElementById("home_care");

    var parts = [];
    if (whatWeDid && whatWeDid.value.trim()) {
        parts.push("WHAT WE DID TODAY\n" + whatWeDid.value.trim());
    }
    if (whatsNext && whatsNext.value.trim()) {
        parts.push("WHAT COMES NEXT\n" + whatsNext.value.trim());
    }
    if (homeCare && homeCare.value.trim()) {
        parts.push("HOME CARE INSTRUCTIONS\n" + homeCare.value.trim());
    }

    var text = parts.join("\n\n");
    var btn = event.currentTarget || event.target;

    copyToClipboard(text).then(function () {
        showCopyFeedback(btn, "Copied!");
    }).catch(function () {
        showCopyFeedback(btn, "Copy failed");
    });
}

// --- Initialization ---

document.addEventListener("DOMContentLoaded", function () {
    // Store original transcript for dirty tracking
    var transcriptArea = document.getElementById("transcript-edit");
    if (transcriptArea) {
        originalTranscript = transcriptArea.value;
    }

    // Auto-resize all textareas on load
    autoResizeAll();

    // Set up tab click handlers
    var tabButtons = document.querySelectorAll(".tab-btn");
    tabButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            var tabId = btn.getAttribute("data-tab");
            switchTab(tabId);
        });
    });

    // Re-auto-resize and restore tab state after HTMX swaps
    document.body.addEventListener("htmx:afterSwap", function () {
        autoResizeAll();
        restoreActiveTab();
    });
});
