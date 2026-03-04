import 'package:dental_notes/network/notes_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Creates a Dio instance that intercepts all requests and returns
/// [responseData] as the response body.
Dio _mockDio(Map<String, dynamic> responseData) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test'));
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) {
      handler.resolve(Response(
        requestOptions: options,
        data: responseData,
        statusCode: 200,
      ),);
    },
  ),);
  return dio;
}

void main() {
  group('generateSoap', () {
    test('parses full SOAP response with nested fields', () async {
      final dio = _mockDio({
        'subjective': 'Patient reports pain in lower right molar.',
        'objective': {
          'clinical_findings': 'Caries on #30 distal.',
          'radiographic_findings': 'Periapical lucency #30.',
          'vitals': null,
        },
        'assessment': 'Irreversible pulpitis #30.',
        'plan': {
          'today': ['Root canal #30'],
          'next_visit': ['Crown prep #30'],
          'patient_instructions': ['Avoid chewing on right side'],
          'cdt_codes': ['D3330'],
        },
        'medication_changes': [
          {
            'drug_name': 'ibuprofen',
            'dose': '600mg',
            'frequency': 'TID×3 days',
            'change_type': 'prescribed',
            'prescribing_note': 'for pain',
          },
        ],
      });

      final api = NotesApi(dio);
      final note = await api.generateSoap(
        'transcript text',
        placeholderVisitId: 42,
      );

      expect(note.visitId, 42);
      expect(note.subjective, 'Patient reports pain in lower right molar.');
      expect(note.objectiveClinical, 'Caries on #30 distal.');
      expect(note.objectiveRadiographic, 'Periapical lucency #30.');
      expect(note.objectiveVitals, isNull);
      expect(note.assessment, 'Irreversible pulpitis #30.');
      expect(note.planToday, ['Root canal #30']);
      expect(note.planNextVisit, ['Crown prep #30']);
      expect(note.planInstructions, ['Avoid chewing on right side']);
      expect(note.cdtCodes, ['D3330']);
      expect(note.medicationChanges.length, 1);
      expect(note.medicationChanges.first.drugName, 'ibuprofen');
      expect(note.medicationChanges.first.dose, '600mg');
      expect(note.medicationChanges.first.changeType, 'prescribed');
    });

    test('handles empty medication_changes', () async {
      final dio = _mockDio({
        'subjective': 'Routine checkup.',
        'objective': {
          'clinical_findings': 'No caries detected.',
          'radiographic_findings': null,
          'vitals': null,
        },
        'assessment': 'Healthy dentition.',
        'plan': {
          'today': ['Prophylaxis'],
          'next_visit': [],
          'patient_instructions': ['Continue brushing 2x daily'],
          'cdt_codes': ['D1110'],
        },
        'medication_changes': [],
      });

      final api = NotesApi(dio);
      final note = await api.generateSoap('transcript');

      expect(note.medicationChanges, isEmpty);
      expect(note.planToday, ['Prophylaxis']);
    });

    test('handles missing medication_changes key', () async {
      final dio = _mockDio({
        'subjective': '',
        'objective': {
          'clinical_findings': '',
          'radiographic_findings': null,
          'vitals': null,
        },
        'assessment': '',
        'plan': {
          'today': [],
          'next_visit': [],
          'patient_instructions': [],
          'cdt_codes': [],
        },
      });

      final api = NotesApi(dio);
      final note = await api.generateSoap('transcript');

      expect(note.medicationChanges, isEmpty);
    });
  });

  group('parsePerio', () {
    test('parses perio readings from API response', () async {
      final dio = _mockDio({
        'readings': [
          {
            'tooth': 14,
            'surface': 'buccal',
            'depths': [3, 2, 4],
            'bop': true,
            'recession': 1,
          },
          {
            'tooth': 19,
            'surface': 'lingual',
            'depths': [2, 2, 3],
            'bop': false,
            'recession': 0,
          },
        ],
        'unparsed_segments': [],
      });

      final api = NotesApi(dio);
      final readings = await api.parsePerio('transcript');

      expect(readings.length, 2);
      expect(readings[0].toothNumber, 14);
      expect(readings[0].surface, 'buccal');
      expect(readings[0].depthMb, 3);
      expect(readings[0].depthB, 2);
      expect(readings[0].depthDb, 4);
      expect(readings[0].bop, true);
      expect(readings[0].recession, 1);

      expect(readings[1].toothNumber, 19);
      expect(readings[1].bop, false);
    });

    test('handles missing bop and recession with defaults', () async {
      final dio = _mockDio({
        'readings': [
          {
            'tooth': 14,
            'surface': 'buccal',
            'depths': [3, 2, 4],
          },
        ],
        'unparsed_segments': [],
      });

      final api = NotesApi(dio);
      final readings = await api.parsePerio('transcript');

      expect(readings.first.bop, false);
      expect(readings.first.recession, 0);
    });
  });

  group('extractMedications', () {
    test('parses medication changes from API response', () async {
      final dio = _mockDio({
        'changes': [
          {
            'drug_name': 'amoxicillin',
            'dose': '500mg',
            'frequency': 'TID×7d',
            'change_type': 'prescribed',
            'prescribing_note': 'prophylaxis',
          },
          {
            'drug_name': 'ibuprofen',
            'dose': '400mg',
            'frequency': 'PRN',
            'change_type': 'prescribed',
          },
        ],
      });

      final api = NotesApi(dio);
      final meds = await api.extractMedications('transcript');

      expect(meds.length, 2);
      expect(meds[0].drugName, 'amoxicillin');
      expect(meds[0].dose, '500mg');
      expect(meds[0].changeType, 'prescribed');
      expect(meds[0].prescribingNote, 'prophylaxis');
      expect(meds[1].drugName, 'ibuprofen');
      expect(meds[1].prescribingNote, isNull);
    });
  });
}
