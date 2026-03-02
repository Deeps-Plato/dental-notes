import 'package:freezed_annotation/freezed_annotation.dart';

part 'soap_note.freezed.dart';
part 'soap_note.g.dart';

@freezed
class MedicationChange with _$MedicationChange {
  const factory MedicationChange({
    required String drugName,
    required String dose,
    required String frequency,
    required String changeType, // prescribed | discontinued | modified | refilled
    String? prescribingNote,
  }) = _MedicationChange;

  factory MedicationChange.fromJson(Map<String, dynamic> json) =>
      _$MedicationChangeFromJson(json);
}

@freezed
class SoapNote with _$SoapNote {
  const factory SoapNote({
    required int id,
    required int visitId,
    required String subjective,
    required String objectiveClinical,
    String? objectiveRadiographic,
    String? objectiveVitals,
    required String assessment,
    required List<String> planToday,
    required List<String> planNextVisit,
    required List<String> planInstructions,
    required List<String> cdtCodes,
    required List<MedicationChange> medicationChanges,
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _SoapNote;

  factory SoapNote.fromJson(Map<String, dynamic> json) => _$SoapNoteFromJson(json);
}
