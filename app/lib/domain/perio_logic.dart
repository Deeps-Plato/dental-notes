import '../core/constants.dart';
import '../data/models/perio_chart.dart';

/// AAP 2017 Classification — Stage and Grade calculation from perio readings.
class PerioLogic {
  PerioLogic._();

  /// Determine AAP Stage (I–IV) from max probing depth and tooth loss count.
  ///
  /// [readings] — all 6-point readings for the patient.
  /// [teethLostDueToPeriodontitis] — count of teeth lost due to perio (not caries/trauma).
  static String calculateStage(
    List<PerioReading> readings, {
    int teethLostDueToPeriodontitis = 0,
  }) {
    if (readings.isEmpty) return 'Undetermined';

    final maxDepth = readings.map(_maxDepth).reduce((a, b) => a > b ? a : b);

    if (teethLostDueToPeriodontitis >= 5 && maxDepth >= 6) return 'IV';
    if (maxDepth >= 6) return 'III';
    if (maxDepth <= AapThresholds.stageIMaxDepth) return 'I';
    if (maxDepth <= AapThresholds.stageIIMaxDepth) return 'II';
    return 'III';
  }

  /// Determine AAP Grade (A–C) from BOP percentage and risk factors.
  ///
  /// [isDiabetic] and [isSmoker] shift grade toward C.
  static String calculateGrade(
    List<PerioReading> readings, {
    bool isDiabetic = false,
    bool isSmoker = false,
  }) {
    if (isDiabetic || isSmoker) return 'C';

    final bopPct = calculateBopPercent(readings);
    if (bopPct <= AapThresholds.gradeAMaxBopPct) return 'A';
    if (bopPct <= AapThresholds.gradeBMaxBopPct) return 'B';
    return 'C';
  }

  /// BOP percentage: sites with BOP / total recorded sites.
  static double calculateBopPercent(List<PerioReading> readings) {
    if (readings.isEmpty) return 0;
    final bopCount = readings.where((r) => r.bop).length;
    // Each reading represents 3 sites
    final totalSites = readings.length * 3;
    // Approximate: weight BOP sites as 3 per tooth/surface
    return bopCount / totalSites;
  }

  /// Maximum depth across the three measurement points of a reading.
  static int _maxDepth(PerioReading r) => [r.depthMb, r.depthB, r.depthDb].reduce(
    (a, b) => a > b ? a : b,
  );

  /// All depths flattened for a reading.
  static List<int> depthsOf(PerioReading r) => [r.depthMb, r.depthB, r.depthDb];
}
