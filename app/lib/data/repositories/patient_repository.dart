import 'package:drift/drift.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../shared/providers/database_provider.dart';
import '../database/app_database.dart';

part 'patient_repository.g.dart';

@riverpod
PatientRepository patientRepository(PatientRepositoryRef ref) {
  final db = ref.watch(databaseProvider);
  return PatientRepository(db);
}

class PatientRepository {
  PatientRepository(this._db);
  final AppDatabase _db;

  /// Watch all patients ordered by last name.
  Stream<List<Patient>> watchAll() {
    final query = _db.select(_db.patients)
      ..orderBy([
        (t) => OrderingTerm(expression: t.lastName),
        (t) => OrderingTerm(expression: t.firstName),
      ]);
    return query.watch();
  }

  /// Watch a single patient by ID.
  Stream<Patient?> watchById(int id) {
    final query = _db.select(_db.patients)
      ..where((t) => t.id.equals(id));
    return query.watchSingleOrNull();
  }

  /// Search patients by first or last name.
  Stream<List<Patient>> watchSearch(String query) {
    final pattern = '%$query%';
    final q = _db.select(_db.patients)
      ..where((t) =>
          t.firstName.like(pattern) | t.lastName.like(pattern),)
      ..orderBy([(t) => OrderingTerm(expression: t.lastName)]);
    return q.watch();
  }

  /// Create a new patient. Returns the auto-generated ID.
  Future<int> create({
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    String? phone,
    String? email,
    String? allergies,
    String? medicalHistory,
  }) async {
    final id = await _db.into(_db.patients).insert(
      PatientsCompanion.insert(
        firstName: firstName,
        lastName: lastName,
        dateOfBirth: dateOfBirth,
        phone: Value.absentIfNull(phone),
        email: Value.absentIfNull(email),
        allergies: Value.absentIfNull(allergies),
        medicalHistory: Value.absentIfNull(medicalHistory),
      ),
    );
    await _audit('create', 'patient', id);
    return id;
  }

  /// Update an existing patient.
  Future<void> update(int id, PatientsCompanion companion) async {
    final updated = companion.copyWith(
      updatedAt: Value(DateTime.now()),
    );
    await (_db.update(_db.patients)..where((t) => t.id.equals(id)))
        .write(updated);
    await _audit('update', 'patient', id);
  }

  /// Delete a patient and all related visits.
  Future<void> delete(int id) async {
    await _audit('delete', 'patient', id);
    await (_db.delete(_db.patients)..where((t) => t.id.equals(id))).go();
  }

  Future<void> _audit(String action, String entityType, int entityId) async {
    await _db.into(_db.auditLogs).insert(
      AuditLogsCompanion.insert(
        action: action,
        entityType: entityType,
        entityId: entityId,
      ),
    );
  }
}
