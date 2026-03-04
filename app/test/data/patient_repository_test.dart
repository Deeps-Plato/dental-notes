import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/repositories/patient_repository.dart';
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

void main() {
  late AppDatabase db;
  late PatientRepository repo;

  setUp(() {
    db = _openTestDb();
    repo = PatientRepository(db);
  });

  tearDown(() => db.close());

  test('create returns auto-generated ID', () async {
    final id = await repo.create(
      firstName: 'Jane',
      lastName: 'Doe',
      dateOfBirth: DateTime(1985, 3, 15),
    );
    expect(id, greaterThan(0));
  });

  test('create with optional fields persists all data', () async {
    final id = await repo.create(
      firstName: 'John',
      lastName: 'Smith',
      dateOfBirth: DateTime(1990, 7, 20),
      phone: '555-1234',
      email: 'john@example.com',
      allergies: 'Penicillin',
      medicalHistory: 'Diabetes Type 2',
    );

    final patients = await db.select(db.patients).get();
    expect(patients.length, 1);
    final p = patients.first;
    expect(p.id, id);
    expect(p.firstName, 'John');
    expect(p.lastName, 'Smith');
    expect(p.phone, '555-1234');
    expect(p.email, 'john@example.com');
    expect(p.allergies, 'Penicillin');
    expect(p.medicalHistory, 'Diabetes Type 2');
  });

  test('watchAll returns patients ordered by last name', () async {
    await repo.create(
      firstName: 'Zara',
      lastName: 'Williams',
      dateOfBirth: DateTime(1995, 1, 1),
    );
    await repo.create(
      firstName: 'Alice',
      lastName: 'Anderson',
      dateOfBirth: DateTime(1988, 6, 10),
    );
    await repo.create(
      firstName: 'Mike',
      lastName: 'Baker',
      dateOfBirth: DateTime(1975, 12, 5),
    );

    final patients = await repo.watchAll().first;
    expect(patients.length, 3);
    expect(patients[0].lastName, 'Anderson');
    expect(patients[1].lastName, 'Baker');
    expect(patients[2].lastName, 'Williams');
  });

  test('watchById returns matching patient', () async {
    final id = await repo.create(
      firstName: 'Test',
      lastName: 'Patient',
      dateOfBirth: DateTime(2000, 1, 1),
    );

    final patient = await repo.watchById(id).first;
    expect(patient, isNotNull);
    expect(patient!.firstName, 'Test');
  });

  test('watchById returns null for nonexistent ID', () async {
    final patient = await repo.watchById(999).first;
    expect(patient, isNull);
  });

  test('watchSearch matches first name', () async {
    await repo.create(
      firstName: 'Alice',
      lastName: 'Smith',
      dateOfBirth: DateTime(1990, 1, 1),
    );
    await repo.create(
      firstName: 'Bob',
      lastName: 'Jones',
      dateOfBirth: DateTime(1990, 1, 1),
    );

    final results = await repo.watchSearch('Ali').first;
    expect(results.length, 1);
    expect(results.first.firstName, 'Alice');
  });

  test('watchSearch matches last name', () async {
    await repo.create(
      firstName: 'Alice',
      lastName: 'Smith',
      dateOfBirth: DateTime(1990, 1, 1),
    );

    final results = await repo.watchSearch('Smi').first;
    expect(results.length, 1);
    expect(results.first.lastName, 'Smith');
  });

  test('watchSearch is case-insensitive', () async {
    await repo.create(
      firstName: 'Alice',
      lastName: 'Smith',
      dateOfBirth: DateTime(1990, 1, 1),
    );

    final results = await repo.watchSearch('alice').first;
    expect(results.length, 1);
  });

  test('update modifies patient fields', () async {
    final id = await repo.create(
      firstName: 'Old',
      lastName: 'Name',
      dateOfBirth: DateTime(1990, 1, 1),
    );

    await repo.update(
      id,
      const PatientsCompanion(firstName: Value('New')),
    );

    final patient = await repo.watchById(id).first;
    expect(patient!.firstName, 'New');
    expect(patient.lastName, 'Name'); // unchanged
  });

  test('delete removes patient', () async {
    final id = await repo.create(
      firstName: 'Delete',
      lastName: 'Me',
      dateOfBirth: DateTime(1990, 1, 1),
    );

    await repo.delete(id);

    final patient = await repo.watchById(id).first;
    expect(patient, isNull);
  });

  test('create writes audit log entry', () async {
    await repo.create(
      firstName: 'Audit',
      lastName: 'Test',
      dateOfBirth: DateTime(1990, 1, 1),
    );

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 1);
    expect(logs.first.action, 'create');
    expect(logs.first.entityType, 'patient');
  });

  test('update writes audit log entry', () async {
    final id = await repo.create(
      firstName: 'A',
      lastName: 'B',
      dateOfBirth: DateTime(1990, 1, 1),
    );
    await repo.update(id, const PatientsCompanion(firstName: Value('C')));

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 2);
    expect(logs[0].action, 'create');
    expect(logs[1].action, 'update');
  });

  test('delete writes audit log entry before deletion', () async {
    final id = await repo.create(
      firstName: 'D',
      lastName: 'E',
      dateOfBirth: DateTime(1990, 1, 1),
    );
    await repo.delete(id);

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 2);
    expect(logs[1].action, 'delete');
    expect(logs[1].entityType, 'patient');
  });
}
