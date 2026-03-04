import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/repositories/patient_repository.dart';
import 'package:dental_notes/features/patients/patients_notifier.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

void main() {
  late AppDatabase db;
  late PatientRepository repo;
  late PatientActions actions;

  setUp(() {
    db = _openTestDb();
    repo = PatientRepository(db);
    actions = PatientActions(repo);
  });

  tearDown(() => db.close());

  test('create returns auto-generated ID', () async {
    final id = await actions.create(
      firstName: 'John',
      lastName: 'Doe',
      dateOfBirth: DateTime(1985, 3, 15),
    );
    expect(id, greaterThan(0));
  });

  test('create persists patient retrievable from repo', () async {
    final id = await actions.create(
      firstName: 'Jane',
      lastName: 'Smith',
      dateOfBirth: DateTime(1990, 7, 22),
      phone: '555-0100',
      email: 'jane@example.com',
    );

    final stream = repo.watchById(id);
    final patient = await stream.first;
    expect(patient, isNotNull);
    expect(patient!.firstName, 'Jane');
    expect(patient.lastName, 'Smith');
    expect(patient.phone, '555-0100');
    expect(patient.email, 'jane@example.com');
  });

  test('create with optional medical fields', () async {
    final id = await actions.create(
      firstName: 'Bob',
      lastName: 'Jones',
      dateOfBirth: DateTime(1975, 11, 1),
      allergies: 'Penicillin',
      medicalHistory: 'Hypertension',
    );

    final patient = await repo.watchById(id).first;
    expect(patient!.allergies, 'Penicillin');
    expect(patient.medicalHistory, 'Hypertension');
  });

  test('delete removes patient', () async {
    final id = await actions.create(
      firstName: 'Temp',
      lastName: 'Patient',
      dateOfBirth: DateTime(2000, 1, 1),
    );

    await actions.delete(id);

    final patient = await repo.watchById(id).first;
    expect(patient, isNull);
  });

  test('create multiple patients and list via repo', () async {
    await actions.create(
      firstName: 'Alice',
      lastName: 'A',
      dateOfBirth: DateTime(1980, 1, 1),
    );
    await actions.create(
      firstName: 'Bob',
      lastName: 'B',
      dateOfBirth: DateTime(1985, 1, 1),
    );

    final patients = await repo.watchAll().first;
    expect(patients.length, 2);
  });

  test('create writes audit log', () async {
    await actions.create(
      firstName: 'Audit',
      lastName: 'Test',
      dateOfBirth: DateTime(1990, 1, 1),
    );

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 1);
    expect(logs.first.action, 'create');
    expect(logs.first.entityType, 'patient');
  });

  test('delete writes audit log', () async {
    final id = await actions.create(
      firstName: 'Del',
      lastName: 'Me',
      dateOfBirth: DateTime(1990, 1, 1),
    );
    await actions.delete(id);

    final logs = await db.select(db.auditLogs).get();
    // 1 (create) + 1 (delete)
    expect(logs.length, 2);
    expect(logs[1].action, 'delete');
    expect(logs[1].entityType, 'patient');
  });
}
