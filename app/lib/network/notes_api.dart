import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../data/models/perio_chart.dart';
import '../data/models/soap_note.dart';
import 'api_client.dart';

part 'notes_api.g.dart';

@riverpod
Future<NotesApi> notesApi(NotesApiRef ref) async {
  final client = await ref.watch(apiClientProvider.future);
  return NotesApi(client.dio);
}

class NotesApi {
  const NotesApi(this._dio);
  final Dio _dio;

  Future<SoapNote> generateSoap(
    String transcript, {
    String? patientContext,
    int placeholderVisitId = 0,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/generate-note',
      data: {
        'note_type': 'soap',
        'transcript': transcript,
        if (patientContext != null) 'patient_context': patientContext,
      },
    );
    final body = response.data!;
    // Map API response → SoapNote model (without a real DB id yet)
    return _parseSoapResponse(body, placeholderVisitId);
  }

  Future<List<PerioReading>> parsePerio(String transcript) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/generate-note',
      data: {
        'note_type': 'perio_parse',
        'transcript': transcript,
      },
    );
    final body = response.data!;
    final readings = (body['readings'] as List).cast<Map<String, dynamic>>();
    return readings
        .map(
          (r) => PerioReading(
            id: 0,
            chartId: 0,
            toothNumber: r['tooth'] as int,
            surface: r['surface'] as String,
            depthMb: (r['depths'] as List)[0] as int,
            depthB: (r['depths'] as List)[1] as int,
            depthDb: (r['depths'] as List)[2] as int,
            bop: r['bop'] as bool? ?? false,
            recession: r['recession'] as int? ?? 0,
          ),
        )
        .toList();
  }

  Future<List<MedicationChange>> extractMedications(String transcript) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/generate-note',
      data: {
        'note_type': 'medication_extract',
        'transcript': transcript,
      },
    );
    final body = response.data!;
    final changes = (body['changes'] as List).cast<Map<String, dynamic>>();
    return changes.map(_parseMedChange).toList();
  }

  SoapNote _parseSoapResponse(Map<String, dynamic> body, int visitId) {
    final objective = body['objective'] as Map<String, dynamic>;
    final plan = body['plan'] as Map<String, dynamic>;
    final meds = (body['medication_changes'] as List? ?? [])
        .cast<Map<String, dynamic>>()
        .map(_parseMedChange)
        .toList();

    return SoapNote(
      id: 0,
      visitId: visitId,
      subjective: body['subjective'] as String? ?? '',
      objectiveClinical: objective['clinical_findings'] as String? ?? '',
      objectiveRadiographic: objective['radiographic_findings'] as String?,
      objectiveVitals: objective['vitals'] as String?,
      assessment: body['assessment'] as String? ?? '',
      planToday: _toStringList(plan['today']),
      planNextVisit: _toStringList(plan['next_visit']),
      planInstructions: _toStringList(plan['patient_instructions']),
      cdtCodes: _toStringList(plan['cdt_codes']),
      medicationChanges: meds,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
  }

  List<String> _toStringList(dynamic value) =>
      (value as List? ?? []).cast<String>();

  /// Parse a medication change from the API's snake_case JSON keys.
  MedicationChange _parseMedChange(Map<String, dynamic> json) =>
      MedicationChange(
        drugName: json['drug_name'] as String,
        dose: json['dose'] as String,
        frequency: json['frequency'] as String,
        changeType: json['change_type'] as String,
        prescribingNote: json['prescribing_note'] as String?,
      );
}
