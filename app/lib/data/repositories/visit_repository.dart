import 'package:drift/drift.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../shared/providers/database_provider.dart';
import '../database/app_database.dart';

part 'visit_repository.g.dart';

@riverpod
VisitRepository visitRepository(VisitRepositoryRef ref) {
  final db = ref.watch(databaseProvider);
  return VisitRepository(db);
}

class VisitRepository {
  VisitRepository(this._db);
  final AppDatabase _db;

  /// Watch all visits for a patient, most recent first.
  Stream<List<Visit>> watchForPatient(int patientId) {
    final query = _db.select(_db.visits)
      ..where((t) => t.patientId.equals(patientId))
      ..orderBy([(t) => OrderingTerm.desc(t.visitDate)]);
    return query.watch();
  }

  /// Get a single visit by ID.
  Future<Visit?> getById(int id) {
    final query = _db.select(_db.visits)
      ..where((t) => t.id.equals(id));
    return query.getSingleOrNull();
  }

  /// Watch a single visit.
  Stream<Visit?> watchById(int id) {
    final query = _db.select(_db.visits)
      ..where((t) => t.id.equals(id));
    return query.watchSingleOrNull();
  }

  /// Create a new visit. Returns the auto-generated ID.
  Future<int> create({
    required int patientId,
    required DateTime visitDate,
    String? chiefComplaint,
    String? provider,
  }) async {
    final id = await _db.into(_db.visits).insert(
      VisitsCompanion.insert(
        patientId: patientId,
        visitDate: visitDate,
        chiefComplaint: Value.absentIfNull(chiefComplaint),
        provider: Value.absentIfNull(provider),
      ),
    );
    await _audit('create', 'visit', id);
    return id;
  }

  /// Save the raw transcript to a visit.
  Future<void> saveTranscript(int visitId, String transcript) async {
    await (_db.update(_db.visits)..where((t) => t.id.equals(visitId))).write(
      VisitsCompanion(
        rawTranscript: Value(transcript),
        updatedAt: Value(DateTime.now()),
      ),
    );
    await _audit('update', 'visit', visitId);
  }

  /// Mark a visit as complete.
  Future<void> markComplete(int visitId) async {
    await (_db.update(_db.visits)..where((t) => t.id.equals(visitId))).write(
      VisitsCompanion(
        isComplete: const Value(true),
        updatedAt: Value(DateTime.now()),
      ),
    );
    await _audit('update', 'visit', visitId);
  }

  /// Delete a visit.
  Future<void> delete(int id) async {
    await _audit('delete', 'visit', id);
    await (_db.delete(_db.visits)..where((t) => t.id.equals(id))).go();
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
