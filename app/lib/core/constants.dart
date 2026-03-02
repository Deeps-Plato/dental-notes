/// Application-wide dental constants.
library;

// ── CDT code catalogue (commonly used) ───────────────────────────────────────

class CdtCodes {
  CdtCodes._();

  static const Map<String, String> all = {
    'D0120': 'Periodic oral evaluation',
    'D0150': 'Comprehensive oral evaluation',
    'D0210': 'Full-mouth radiographic series',
    'D0220': 'Periapical radiograph — first image',
    'D0230': 'Periapical radiograph — each additional',
    'D0272': 'Bitewing radiographs — two images',
    'D0274': 'Bitewing radiographs — four images',
    'D1110': 'Prophylaxis — adult',
    'D1120': 'Prophylaxis — child',
    'D1208': 'Topical fluoride — office procedure',
    'D1351': 'Sealant — per tooth',
    'D2140': 'Amalgam restoration — one surface, primary or permanent',
    'D2160': 'Amalgam restoration — two surfaces, primary or permanent',
    'D2161': 'Amalgam restoration — three or more surfaces, primary or permanent',
    'D2330': 'Resin-based composite — one surface, anterior',
    'D2331': 'Resin-based composite — two surfaces, anterior',
    'D2332': 'Resin-based composite — three surfaces, anterior',
    'D2335': 'Resin-based composite — four or more surfaces or involving incisal angle',
    'D2391': 'Resin-based composite — one surface, posterior',
    'D2392': 'Resin-based composite — two surfaces, posterior',
    'D2393': 'Resin-based composite — three surfaces, posterior',
    'D2394': 'Resin-based composite — four or more surfaces, posterior',
    'D2710': 'Crown — resin-based composite (indirect)',
    'D2740': 'Crown — porcelain/ceramic substrate',
    'D2750': 'Crown — porcelain fused to high noble metal',
    'D2780': 'Crown — 3/4 cast high noble metal',
    'D2930': 'Prefabricated stainless steel crown — primary tooth',
    'D3310': 'Endodontic therapy — anterior tooth (excluding final restoration)',
    'D3320': 'Endodontic therapy — premolar tooth',
    'D3330': 'Endodontic therapy — molar tooth',
    'D4341': 'Periodontal scaling and root planing — four or more teeth per quadrant',
    'D4342': 'Periodontal scaling and root planing — one to three teeth per quadrant',
    'D4910': 'Periodontal maintenance',
    'D7140': 'Extraction, erupted tooth or exposed root',
    'D7210': 'Extraction, erupted tooth requiring elevation of mucoperiosteal flap',
    'D9930': 'Treatment of complications (post-surgical) — unusual circumstances',
  };
}

// ── Tooth numbering — Universal system ───────────────────────────────────────

class ToothNumbering {
  ToothNumbering._();

  /// All tooth numbers 1–32.
  static const List<int> all = [
    1, 2, 3, 4, 5, 6, 7, 8,
    9, 10, 11, 12, 13, 14, 15, 16,
    17, 18, 19, 20, 21, 22, 23, 24,
    25, 26, 27, 28, 29, 30, 31, 32,
  ];

  /// Upper arch (maxillary): 1–16 right to left.
  static const List<int> upper = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];

  /// Lower arch (mandibular): 17–32 left to right.
  static const List<int> lower = [32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17];

  static String name(int tooth) {
    const names = {
      1: 'UR3M', 2: 'UR2M', 3: 'UR1M', 4: 'UR2PM', 5: 'UR1PM',
      6: 'URC', 7: 'URL1', 8: 'URI1', 9: 'ULI1', 10: 'ULL1',
      11: 'ULC', 12: 'UL1PM', 13: 'UL2PM', 14: 'UL1M', 15: 'UL2M', 16: 'UL3M',
      17: 'LL3M', 18: 'LL2M', 19: 'LL1M', 20: 'LL2PM', 21: 'LL1PM',
      22: 'LLC', 23: 'LLL1', 24: 'LLI1', 25: 'LRI1', 26: 'LRL1',
      27: 'LRC', 28: 'LR1PM', 29: 'LR2PM', 30: 'LR1M', 31: 'LR2M', 32: 'LR3M',
    };
    return names[tooth] ?? '#$tooth';
  }
}

// ── AAP Staging thresholds ────────────────────────────────────────────────────

class AapThresholds {
  AapThresholds._();

  static const int stageIMaxDepth = 4;
  static const int stageIIMaxDepth = 5;
  // Stage III: max depth ≥6 mm
  // Stage IV: max depth ≥6 mm AND ≥5 teeth lost due to periodontitis

  static const double gradeAMaxBopPct = 0.10;  // <10% BOP
  static const double gradeBMaxBopPct = 0.30;  // 10–30% BOP
  // Grade C: >30% BOP or systemic risk factors (diabetes, smoking)
}
