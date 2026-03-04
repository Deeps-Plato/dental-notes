import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/repositories/visit_repository.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

void main() {
  late AppDatabase db;
  late VisitRepository repo;

  setUp(() async {
    db = _openTestDb();
    repo = VisitRepository(db);

    // Insert a patient for FK constraints.
    await db.into(db.patients).insert(PatientsCompanion.insert(
      firstName: 'Test',
      lastName: 'Patient',
      dateOfBirth: DateTime(1990, 1, 1),
    ),);
  });

  tearDown(() => db.close());

  test('create returns auto-generated ID', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );
    expect(id, greaterThan(0));
  });

  test('create with optional fields persists all data', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
      chiefComplaint: 'Toothache',
      provider: 'Dr. Smith',
    );

    final visit = await repo.getById(id);
    expect(visit, isNotNull);
    expect(visit!.chiefComplaint, 'Toothache');
    expect(visit.provider, 'Dr. Smith');
    expect(visit.isComplete, false);
    expect(visit.rawTranscript, isNull);
  });

  test('getById returns null for nonexistent visit', () async {
    final visit = await repo.getById(999);
    expect(visit, isNull);
  });

  test('watchForPatient returns visits ordered most recent first', () async {
    await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 1, 10),
    );
    await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );
    await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 3, 20),
    );

    final visits = await repo.watchForPatient(1).first;
    expect(visits.length, 3);
    // Most recent first
    expect(visits[0].visitDate, DateTime(2024, 6, 15));
    expect(visits[1].visitDate, DateTime(2024, 3, 20));
    expect(visits[2].visitDate, DateTime(2024, 1, 10));
  });

  test('watchForPatient returns empty for patient with no visits', () async {
    final visits = await repo.watchForPatient(1).first;
    expect(visits, isEmpty);
  });

  test('watchById returns matching visit', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );

    final visit = await repo.watchById(id).first;
    expect(visit, isNotNull);
    expect(visit!.patientId, 1);
  });

  test('saveTranscript persists raw transcript', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );

    await repo.saveTranscript(id, 'Patient reports toothache on lower right.');

    final visit = await repo.getById(id);
    expect(visit!.rawTranscript, 'Patient reports toothache on lower right.');
  });

  test('markComplete sets isComplete to true', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );

    await repo.markComplete(id);

    final visit = await repo.getById(id);
    expect(visit!.isComplete, true);
  });

  test('delete removes visit', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );

    await repo.delete(id);

    final visit = await repo.getById(id);
    expect(visit, isNull);
  });

  test('create writes audit log', () async {
    await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 1);
    expect(logs.first.action, 'create');
    expect(logs.first.entityType, 'visit');
  });

  test('saveTranscript writes update audit log', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );
    await repo.saveTranscript(id, 'transcript text');

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 2);
    expect(logs[1].action, 'update');
    expect(logs[1].entityType, 'visit');
  });

  test('markComplete writes update audit log', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );
    await repo.markComplete(id);

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 2);
    expect(logs[1].action, 'update');
  });

  test('delete writes audit log before removal', () async {
    final id = await repo.create(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    );
    await repo.delete(id);

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 2);
    expect(logs[1].action, 'delete');
    expect(logs[1].entityType, 'visit');
  });
}
