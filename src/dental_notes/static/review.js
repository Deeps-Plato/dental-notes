/**
 * Review page JavaScript: clipboard copy, dirty tracking, auto-resize.
 *
 * Handles:
 * - Copy All: fetches server-formatted text via /api/session/{id}/note-text
 * - Per-section copy: reads textarea value and copies with section header
 * - Transcript dirty tracking: shows regen banner when transcript changes
 * - Auto-resize textareas: adjusts height to content on load and input
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

// --- Initialization ---

document.addEventListener("DOMContentLoaded", function () {
    // Store original transcript for dirty tracking
    var transcriptArea = document.getElementById("transcript-edit");
    if (transcriptArea) {
        originalTranscript = transcriptArea.value;
    }

    // Auto-resize all textareas on load
    autoResizeAll();

    // Re-auto-resize after HTMX swaps (e.g., after extraction)
    document.body.addEventListener("htmx:afterSwap", function () {
        autoResizeAll();
    });
});
