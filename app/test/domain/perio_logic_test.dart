import 'package:dental_notes/domain/perio_logic.dart';
import 'package:dental_notes/data/models/perio_chart.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('PerioLogic.calculateStage', () {
    test('empty readings → Undetermined', () {
      expect(PerioLogic.calculateStage([]), 'Undetermined');
    });

    test('max depth ≤4 → Stage I', () {
      final readings = [_r(3, 3, 3), _r(4, 2, 2)];
      expect(PerioLogic.calculateStage(readings), 'I');
    });

    test('max depth 5 → Stage II', () {
      final readings = [_r(5, 3, 3)];
      expect(PerioLogic.calculateStage(readings), 'II');
    });

    test('max depth 6 → Stage III', () {
      final readings = [_r(6, 3, 3)];
      expect(PerioLogic.calculateStage(readings), 'III');
    });

    test('max depth 6 + 5 teeth lost → Stage IV', () {
      final readings = [_r(6, 3, 3)];
      expect(
        PerioLogic.calculateStage(readings, teethLostDueToPeriodontitis: 5),
        'IV',
      );
    });
  });

  group('PerioLogic.calculateBopPercent', () {
    test('no BOP → 0', () {
      final readings = [_r(3, 3, 3, bop: false)];
      expect(PerioLogic.calculateBopPercent(readings), closeTo(0, 0.01));
    });

    test('all BOP → 1/3 (1 bop site / 3 total sites per reading)', () {
      final readings = [_r(3, 3, 3, bop: true)];
      expect(PerioLogic.calculateBopPercent(readings), closeTo(1 / 3, 0.01));
    });
  });

  group('PerioLogic.calculateGrade', () {
    test('diabetic → Grade C', () {
      expect(
        PerioLogic.calculateGrade([], isDiabetic: true),
        'C',
      );
    });

    test('smoker → Grade C', () {
      expect(
        PerioLogic.calculateGrade([], isSmoker: true),
        'C',
      );
    });

    test('low BOP → Grade A', () {
      // All shallow, no BOP → BOP% = 0 → A
      final readings = List.generate(20, (_) => _r(2, 2, 2, bop: false));
      expect(PerioLogic.calculateGrade(readings), 'A');
    });
  });
}

PerioReading _r(int mb, int b, int db, {bool bop = false}) => PerioReading(
  id: 0,
  chartId: 0,
  toothNumber: 14,
  surface: 'buccal',
  depthMb: mb,
  depthB: b,
  depthDb: db,
  bop: bop,
  recession: 0,
);
