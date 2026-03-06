"""Word-level overlap deduplication at chunk transcript boundaries.

When audio chunks are produced with ~1s overlap, the same words may appear
at the end of one transcript and the start of the next. This module removes
the duplicated prefix from the new chunk's transcript.

Uses simple word-level matching (not fuzzy). Research acknowledges this may
need fuzzy matching later, but exact matching is the correct starting point.
"""


def deduplicate_overlap(
    prev_text: str,
    new_text: str,
    max_overlap_words: int = 10,
) -> str:
    """Remove overlapping words between previous and new transcript chunks.

    Compares the tail of prev_text (up to max_overlap_words) with the head
    of new_text. Finds the longest matching suffix of prev_tail that equals
    a prefix of new_text, then returns new_text with that prefix removed.

    Args:
        prev_text: Transcript from the previous chunk.
        new_text: Transcript from the current chunk.
        max_overlap_words: Maximum number of trailing words to compare.

    Returns:
        new_text with any overlapping prefix words removed.
    """
    if not prev_text or not new_text:
        return new_text

    prev_words = prev_text.split()
    new_words = new_text.split()

    if not prev_words or not new_words:
        return new_text

    # Take the tail of previous text (up to max_overlap_words)
    tail = prev_words[-max_overlap_words:]

    # Try matching progressively shorter suffixes of tail against prefix of new
    best_match_len = 0
    for start in range(len(tail)):
        suffix = tail[start:]
        suffix_len = len(suffix)

        if suffix_len > len(new_words):
            continue

        if suffix == new_words[:suffix_len]:
            best_match_len = max(best_match_len, suffix_len)

    if best_match_len > 0:
        return " ".join(new_words[best_match_len:])

    return new_text
