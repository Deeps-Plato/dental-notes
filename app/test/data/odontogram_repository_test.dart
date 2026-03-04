import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/models/odontogram.dart' as models;
import 'package:dental_notes/data/repositories/odontogram_repository.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

void main() {
  late AppDatabase db;
  late OdontogramRepository repo;

  setUp(() async {
    db = _openTestDb();
    repo = OdontogramRepository(db);

    // Insert a patient and visit for FK constraints.
    await db.into(db.patients).insert(PatientsCompanion.insert(
      firstName: 'Test',
      lastName: 'Patient',
      dateOfBirth: DateTime(1990, 1, 1),
    ),);
    await db.into(db.visits).insert(VisitsCompanion.insert(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    ),);
  });

  tearDown(() => db.close());

  test('getForVisit returns null when no odontogram exists', () async {
    final result = await repo.getForVisit(1);
    expect(result, isNull);
  });

  test('save creates and getForVisit retrieves odontogram', () async {
    const odontogram = models.Odontogram(
      visitId: 1,
      teeth: {
        14: models.ToothRecord(
          toothNumber: 14,
          surfaces: [
            models.SurfaceCondition(
              surface: models.ToothSurface.occlusal,
              condition: models.ConditionType.caries,
            ),
          ],
        ),
      },
    );

    await repo.save(odontogram);

    final retrieved = await repo.getForVisit(1);
    expect(retrieved, isNotNull);
    expect(retrieved!.visitId, 1);
    expect(retrieved.teeth.length, 1);
    expect(retrieved.teeth[14]!.toothNumber, 14);
    expect(
      retrieved.teeth[14]!.surfaces.first.condition,
      models.ConditionType.caries,
    );
  });

  test('save updates existing odontogram', () async {
    // Create initial.
    await repo.save(const models.Odontogram(
      visitId: 1,
      teeth: {
        14: models.ToothRecord(
          toothNumber: 14,
          surfaces: [
            models.SurfaceCondition(
              surface: models.ToothSurface.occlusal,
              condition: models.ConditionType.caries,
            ),
          ],
        ),
      },
    ),);

    // Update with additional tooth.
    await repo.save(const models.Odontogram(
      visitId: 1,
      teeth: {
        14: models.ToothRecord(
          toothNumber: 14,
          surfaces: [
            models.SurfaceCondition(
              surface: models.ToothSurface.occlusal,
              condition: models.ConditionType.existingRestoration,
              material: models.RestorativeMaterial.composite,
            ),
          ],
        ),
        19: models.ToothRecord(
          toothNumber: 19,
          surfaces: [
            models.SurfaceCondition(
              surface: models.ToothSurface.mesial,
              condition: models.ConditionType.caries,
            ),
          ],
        ),
      },
    ),);

    final retrieved = await repo.getForVisit(1);
    expect(retrieved!.teeth.length, 2);
    expect(
      retrieved.teeth[14]!.surfaces.first.condition,
      models.ConditionType.existingRestoration,
    );
    expect(
      retrieved.teeth[14]!.surfaces.first.material,
      models.RestorativeMaterial.composite,
    );
    expect(retrieved.teeth[19], isNotNull);
  });

  test('save writes audit log entry', () async {
    await repo.save(const models.Odontogram(visitId: 1, teeth: {}));

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 1);
    expect(logs.first.action, 'create');
    expect(logs.first.entityType, 'odontogram');
  });

  test('update writes update audit log entry', () async {
    await repo.save(const models.Odontogram(visitId: 1, teeth: {}));
    await repo.save(const models.Odontogram(visitId: 1, teeth: {}));

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 2);
    expect(logs[0].action, 'create');
    expect(logs[1].action, 'update');
  });
}
