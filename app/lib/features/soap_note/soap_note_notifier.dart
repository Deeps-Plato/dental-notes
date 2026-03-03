import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/database/app_database.dart';
import '../../data/repositories/soap_note_repository.dart';

part 'soap_note_notifier.g.dart';

/// Watch the SOAP note for a visit — updates in real time as edits are saved.
@riverpod
Stream<SoapNote?> soapNoteForVisit(SoapNoteForVisitRef ref, int visitId) {
  final repo = ref.watch(soapNoteRepositoryProvider);
  return repo.watchForVisit(visitId);
}

/// Actions for editing individual SOAP note fields.
@riverpod
SoapNoteActions soapNoteActions(SoapNoteActionsRef ref) {
  final repo = ref.watch(soapNoteRepositoryProvider);
  return SoapNoteActions(repo);
}

class SoapNoteActions {
  SoapNoteActions(this._repo);
  final SoapNoteRepository _repo;

  Future<void> updateSubjective(int noteId, String value) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        subjective: Value(value),
      ),);

  Future<void> updateObjectiveClinical(int noteId, String value) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        objectiveClinical: Value(value),
      ),);

  Future<void> updateObjectiveRadiographic(int noteId, String? value) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        objectiveRadiographic: Value.absentIfNull(value),
      ),);

  Future<void> updateAssessment(int noteId, String value) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        assessment: Value(value),
      ),);

  Future<void> updatePlanToday(int noteId, List<String> items) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        planToday: Value(jsonEncode(items)),
      ),);

  Future<void> updatePlanNextVisit(int noteId, List<String> items) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        planNextVisit: Value(jsonEncode(items)),
      ),);

  Future<void> updatePlanInstructions(int noteId, List<String> items) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        planInstructions: Value(jsonEncode(items)),
      ),);

  Future<void> updateCdtCodes(int noteId, List<String> codes) =>
      _repo.updateFields(noteId, SoapNotesCompanion(
        cdtCodes: Value(jsonEncode(codes)),
      ),);
}
