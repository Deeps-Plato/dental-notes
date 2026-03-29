"""Dental vocabulary management for Whisper transcription.

Manages the initial_prompt vocabulary, template-specific hotwords,
and custom vocab file loading for faster-whisper.

Token budget: ~224 tokens for initial_prompt (~896 chars).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Comprehensive dental vocabulary prompt for Whisper initial_prompt.
# Covers 4 locked categories: anesthetics/meds, materials/brands,
# pathology/findings, anatomy/surfaces. Plus core terms (tooth numbering,
# surfaces, procedures, CDT codes).
# Budget: ~224 tokens (~896 chars). Prioritizes most-misrecognized terms.
DENTAL_INITIAL_PROMPT = (
    "Dental clinical appointment transcription. "
    # Tooth numbering (compact)
    "Teeth 1 through 32. "
    # Surfaces
    "Mesial, occlusal, distal, buccal, lingual, facial, incisal. "
    "MOD, DO, BL, MO, MODBL. "
    # Anesthetics/meds (CLI-05 expansion)
    "Lidocaine, Septocaine, Marcaine, articaine, epinephrine, "
    "one-to-one-hundred-thousand, ibuprofen, amoxicillin, clindamycin. "
    # Materials/brands (CLI-05 expansion)
    "Herculite, Estelite, Paracore, Luxatemp, Fuji, IRM, Dycal, "
    "composite, amalgam, zirconia, e.max, PFM, lithium disilicate, "
    "Filtek, Shofu, Ivoclar, RelyX, Gluma, Kerr. "
    # Pathology/findings (CLI-05 expansion)
    "Caries, radiolucency, periapical, dehiscence, fenestration, "
    "abscess, calculus, gingivitis, periodontitis, BOP. "
    # Anatomy/surfaces (CLI-05 expansion)
    "CEJ, furcation, mandibular canal, mental foramen, "
    "gingival margin, recession, mobility, probing depths. "
    # Procedures (compact)
    "SRP, scaling, prophy, root canal, obturation, gutta-percha, "
    "crown, bridge, veneer, extraction, implant, denture, sealant. "
    # CDT codes
    "CDT code D0120, D0150, D1110, D2391, D2740, D3330, D4341, D7210."
)

# Template-specific hotwords for faster-whisper's hotwords parameter.
# Each key maps an appointment type to space-separated terms that get
# probability boosting during transcription.
TEMPLATE_HOTWORDS: dict[str, str] = {
    "comprehensive_exam": (
        "comprehensive exam periodic evaluation radiograph bitewing "
        "panoramic periapical probing BOP recession furcation mobility "
        "caries calculus gingivitis periodontitis oral cancer screening "
        "TMJ bruxism occlusion malocclusion"
    ),
    "restorative": (
        "composite amalgam crown bridge veneer onlay inlay prep etch bond "
        "shade Herculite Estelite Filtek e.max zirconia PFM "
        "Lidocaine Septocaine Marcaine articaine anesthetic "
        "matrix band wedge curing light isolation rubber dam"
    ),
    "hygiene_recall": (
        "prophy prophylaxis SRP scaling root planing ultrasonic cavitron "
        "calculus plaque BOP bleeding probing depths recession "
        "fluoride sealant home care flossing Waterpik chlorhexidine "
        "gingivitis periodontitis"
    ),
    "endodontic": (
        "root canal pulpectomy pulpotomy access opening working length "
        "obturation gutta-percha apex locator files rotary "
        "periapical radiolucency abscess vitality cold test electric "
        "calcium hydroxide MTA sealer"
    ),
    "oral_surgery": (
        "extraction simple surgical impacted bone graft socket preservation "
        "sutures hemostasis forceps elevators luxation alveoloplasty "
        "biopsy incision drainage abscess dry socket "
        "Marcaine Lidocaine epinephrine gauze"
    ),
    "general": (
        "composite crown bridge extraction root canal prophy SRP "
        "Lidocaine Septocaine caries periapical radiolucency "
        "probing BOP recession furcation"
    ),
}


def load_custom_vocab(path: Path) -> str:
    """Load custom vocabulary terms from a plain text file.

    File format: one term per line, # for comments, blank lines ignored.

    Args:
        path: Path to the vocab file.

    Returns:
        Space-separated string of terms, or empty string if file missing.
    """
    if not path.exists():
        return ""

    terms: list[str] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            terms.append(stripped)
    except OSError:
        logger.warning("Failed to read custom vocab file: %s", path)
        return ""

    return " ".join(terms)


def build_initial_prompt(custom_vocab_path: Path | None = None) -> str:
    """Build the full Whisper initial_prompt by merging base and custom vocab.

    Args:
        custom_vocab_path: Optional path to a custom vocab file.
            If None or file doesn't exist, returns base prompt only.

    Returns:
        Combined initial_prompt string.
    """
    prompt = DENTAL_INITIAL_PROMPT

    if custom_vocab_path is not None:
        custom = load_custom_vocab(custom_vocab_path)
        if custom:
            prompt = f"{prompt} {custom}"

    token_estimate = len(prompt) / 4
    if token_estimate > 224:
        logger.warning(
            "Combined initial_prompt estimated at %.0f tokens "
            "(limit ~224). Consider trimming custom vocab.",
            token_estimate,
        )

    return prompt
