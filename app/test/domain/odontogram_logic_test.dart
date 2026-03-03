import 'package:dental_notes/domain/odontogram_logic.dart';
import 'package:dental_notes/data/models/odontogram.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('OdontogramLogic.suggestCdtCodes', () {
    test('empty odontogram → no codes', () {
      const odontogram = Odontogram(visitId: 1, teeth: {});
      expect(OdontogramLogic.suggestCdtCodes(odontogram), isEmpty);
    });

    test('posterior composite → D2391', () {
      const odontogram = Odontogram(
        visitId: 1,
        teeth: {
          14: ToothRecord(
            toothNumber: 14,
            surfaces: [
              SurfaceCondition(
                surface: ToothSurface.occlusal,
                condition: ConditionType.proposedRestoration,
                material: RestorativeMaterial.composite,
              ),
            ],
          ),
        },
      );
      final codes = OdontogramLogic.suggestCdtCodes(odontogram);
      expect(codes, contains('D2391'));
    });

    test('anterior composite → D2330', () {
      const odontogram = Odontogram(
        visitId: 1,
        teeth: {
          8: ToothRecord(
            toothNumber: 8,
            surfaces: [
              SurfaceCondition(
                surface: ToothSurface.facial,
                condition: ConditionType.proposedRestoration,
                material: RestorativeMaterial.composite,
              ),
            ],
          ),
        },
      );
      final codes = OdontogramLogic.suggestCdtCodes(odontogram);
      expect(codes, contains('D2330'));
    });

    test('missing tooth → no code', () {
      const odontogram = Odontogram(
        visitId: 1,
        teeth: {
          1: ToothRecord(
            toothNumber: 1,
            surfaces: [
              SurfaceCondition(
                surface: ToothSurface.occlusal,
                condition: ConditionType.missing,
              ),
            ],
          ),
        },
      );
      expect(OdontogramLogic.suggestCdtCodes(odontogram), isEmpty);
    });
  });

  group('OdontogramLogic.surfaceLabel', () {
    test('mesial → M', () => expect(OdontogramLogic.surfaceLabel(ToothSurface.mesial), 'M'));
    test('occlusal → O', () => expect(OdontogramLogic.surfaceLabel(ToothSurface.occlusal), 'O'));
  });
}
