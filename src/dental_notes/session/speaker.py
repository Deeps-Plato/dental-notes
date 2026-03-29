"""Text-based speaker classification for dental appointments.

Classifies transcribed text chunks as Doctor, Patient, or Assistant
based on keyword patterns. The doctor uses clinical terminology; the
patient describes symptoms in lay language; the assistant handles
instruments, patient comfort, procedural assists, and charting.
"""

import re

_DOCTOR_PATTERNS = [
    r"\btooth\s+\d+\b",
    r"#\d{1,2}\b",
    r"\b(?:MOD|MO|DO|OL|BL|DI|MI|MODBL)\b",
    r"\bD\d{4}\b",
    r"\b(?:crown|bridge|veneer|onlay|inlay|composite|amalgam|extraction|"
    r"implant|root canal|pulpectomy|SRP|scaling|prophy|prophylaxis|"
    r"obturation|bone graft|sutures?|abutment|denture)\b",
    r"\b(?:zirconia|e\.?max|PFM|lithium disilicate|Filtek|Shofu|Ivoclar|"
    r"gutta.?percha|RelyX|Gluma|Dentsply|Kerr)\b",
    r"\b(?:caries|abscess|periapical|radiolucency|calculus|furcation|"
    r"recession|mobility|gingivitis|periodontitis|malocclusion|bruxism|"
    r"pocket depth|probing|bleeding on probing|BOP)\b",
    r"\b(?:I (?:see|recommend|suggest)|let'?s|we'?ll|the plan is|"
    r"diagnosis|prognosis|treatment plan|prep|restore|cement)\b",
    r"\b(?:open wider|bite down|rinse|turn (?:left|right)|close)\b",
]

_PATIENT_PATTERNS = [
    r"\b(?:hurts?|painful?|sensitive|bothers?|swollen|bleeding|"
    r"aching?|throbbing|sore|tender|numb)\b",
    r"\b(?:I (?:feel|noticed|think|have|had|was)|it'?s been|"
    r"my (?:tooth|gums?|mouth|jaw))\b",
    r"\b(?:is that|will it|how long|do I need|what about|can I|"
    r"how much|does insurance|when can)\b",
    r"\b(?:okay|alright|sounds good|I understand|got it|thank you|thanks)\b",
]

_ASSISTANT_PATTERNS = [
    # Instrument/supply calls
    r"\b(?:suction|two.by.two|explorer|cotton roll|bite block|"
    r"matrix band|wedge|retractor|high.speed|slow.speed|handpiece)\b",
    # Patient comfort
    r"\byou'?re doing (?:great|well|good)\b",
    r"\balmost done\b",
    r"\brinse and spit\b",
    r"\bare you (?:okay|alright|comfortable)\b",
    r"\bjust a little (?:more|longer)\b",
    # Procedural assists
    r"\b(?:isolation complete|impression set|light cure|mixing|"
    r"loaded|placed|seated|cement mixed)\b",
    r"\b(?:ready (?:for|to))\b",
    # Charting/admin
    r"\b(?:noted|got it|which tooth|what shade)\b",
    r"\b(?:want me to|should I|do you need)\b",
]

_doctor_re = [re.compile(p, re.IGNORECASE) for p in _DOCTOR_PATTERNS]
_patient_re = [re.compile(p, re.IGNORECASE) for p in _PATIENT_PATTERNS]
_assistant_re = [re.compile(p, re.IGNORECASE) for p in _ASSISTANT_PATTERNS]


def classify_speaker(text: str, prev_speaker: str | None = None) -> str:
    """Classify a text chunk as 'Doctor', 'Patient', or 'Assistant'.

    Scores text against doctor, patient, and assistant keyword patterns.
    Falls back to alternating from previous speaker if ambiguous.
    Defaults to 'Doctor' if no context available.

    Tie-breaking: if assistant_score ties with doctor_score (and both
    >= patient_score), returns 'Doctor' per locked decision.
    """
    doctor_score = sum(len(r.findall(text)) for r in _doctor_re)
    patient_score = sum(len(r.findall(text)) for r in _patient_re)
    assistant_score = sum(len(r.findall(text)) for r in _assistant_re)

    max_score = max(doctor_score, patient_score, assistant_score)

    if max_score == 0:
        # All zero -- alternate from previous speaker
        if prev_speaker == "Doctor":
            return "Patient"
        if prev_speaker == "Patient":
            return "Doctor"
        return "Doctor"

    # Tie-breaking: doctor wins ties with assistant (locked decision)
    if doctor_score >= assistant_score and doctor_score >= patient_score:
        return "Doctor"
    if patient_score > doctor_score and patient_score >= assistant_score:
        return "Patient"
    if assistant_score > doctor_score and assistant_score >= patient_score:
        return "Assistant"

    # Fallback (shouldn't reach here, but safety)
    return "Doctor"
