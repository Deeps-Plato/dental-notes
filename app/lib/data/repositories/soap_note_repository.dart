import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../shared/providers/database_provider.dart';
import '../database/app_database.dart';
import '../models/soap_note.dart' as models;

part 'soap_note_repository.g.dart';

@riverpod
SoapNoteRepository soapNoteRepository(SoapNoteRepositoryRef ref) {
  final db = ref.watch(databaseProvider);
  return SoapNoteRepository(db);
}

class SoapNoteRepository {
  SoapNoteRepository(this._db);
  final AppDatabase _db;

  /// Watch the SOAP note for a visit (one note per visit).
  Stream<SoapNote?> watchForVisit(int visitId) {
    final query = _db.select(_db.soapNotes)
      ..where((t) => t.visitId.equals(visitId));
    return query.watchSingleOrNull();
  }

  /// Get the SOAP note for a visit.
  Future<SoapNote?> getForVisit(int visitId) {
    final query = _db.select(_db.soapNotes)
      ..where((t) => t.visitId.equals(visitId));
    return query.getSingleOrNull();
  }

  /// Save or update the SOAP note for a visit.
  ///
  /// If a note already exists for the visit, it is replaced.
  Future<int> save({
    required int visitId,
    required models.SoapNote note,
  }) async {
    // Delete any existing note for this visit
    await (_db.delete(_db.soapNotes)
          ..where((t) => t.visitId.equals(visitId)))
        .go();

    final id = await _db.into(_db.soapNotes).insert(
      SoapNotesCompanion.insert(
        visitId: visitId,
        subjective: Value(note.subjective),
        objectiveClinical: Value(note.objectiveClinical),
        objectiveRadiographic: Value.absentIfNull(note.objectiveRadiographic),
        objectiveVitals: Value.absentIfNull(note.objectiveVitals),
        assessment: Value(note.assessment),
        planToday: Value(jsonEncode(note.planToday)),
        planNextVisit: Value(jsonEncode(note.planNextVisit)),
        planInstructions: Value(jsonEncode(note.planInstructions)),
        cdtCodes: Value(jsonEncode(note.cdtCodes)),
        medicationChanges: Value(jsonEncode(
          note.medicationChanges.map((m) => m.toJson()).toList(),
        ),),
      ),
    );
    await _audit('create', 'soap_note', id);
    return id;
  }

  /// Update individual fields of an existing SOAP note.
  Future<void> updateFields(int noteId, SoapNotesCompanion companion) async {
    final updated = companion.copyWith(
      updatedAt: Value(DateTime.now()),
    );
    await (_db.update(_db.soapNotes)..where((t) => t.id.equals(noteId)))
        .write(updated);
    await _audit('update', 'soap_note', noteId);
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
