import '../core/constants.dart';
import '../data/models/odontogram.dart';

/// Business logic for odontogram — CDT code suggestions, surface notation.
class OdontogramLogic {
  OdontogramLogic._();

  /// Suggest CDT codes based on the conditions recorded in the odontogram.
  static List<String> suggestCdtCodes(Odontogram odontogram) {
    final codes = <String>{};

    for (final tooth in odontogram.teeth.values) {
      for (final surface in tooth.surfaces) {
        final code = _suggestCode(surface, tooth.toothNumber);
        if (code != null) codes.add(code);
      }
    }

    return codes.toList()..sort();
  }

  static String? _suggestCode(SurfaceCondition surface, int toothNumber) {
    if (surface.condition == ConditionType.missing ||
        surface.condition == ConditionType.extracted) {
      return null; // Extraction is recorded at procedure time
    }

    final isAnterior = _isAnterior(toothNumber);

    if (surface.condition == ConditionType.proposedRestoration) {
      if (surface.material == RestorativeMaterial.composite) {
        return isAnterior ? 'D2330' : 'D2391';
      }
      if (surface.material == RestorativeMaterial.amalgam) {
        return 'D2140';
      }
    }

    if (surface.condition == ConditionType.crown) {
      if (surface.material == RestorativeMaterial.porcelain) return 'D2740';
      if (surface.material == RestorativeMaterial.gold) return 'D2780';
    }

    return null;
  }

  /// Universal numbering: teeth 6–11 and 22–27 are anterior.
  static bool _isAnterior(int tooth) =>
      (tooth >= 6 && tooth <= 11) || (tooth >= 22 && tooth <= 27);

  /// Human-readable surface label for UI display.
  static String surfaceLabel(ToothSurface surface) => switch (surface) {
    ToothSurface.mesial => 'M',
    ToothSurface.distal => 'D',
    ToothSurface.occlusal => 'O',
    ToothSurface.facial => 'F',
    ToothSurface.lingual => 'L',
  };
}
