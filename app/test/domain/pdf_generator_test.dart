import 'dart:convert';

import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/domain/pdf_generator.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('PdfGenerator', () {
    late Visit visit;

    setUp(() {
      visit = Visit(
        id: 1,
        patientId: 1,
        visitDate: DateTime(2024, 6, 15),
        chiefComplaint: 'Toothache',
        provider: 'Dr. Smith',
        rawTranscript: null,
        isComplete: false,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );
    });

    test('generatePlaceholder returns valid PDF bytes', () async {
      final bytes = await PdfGenerator.generatePlaceholder();
      // PDF starts with %PDF magic bytes
      expect(bytes.length, greaterThan(100));
      expect(String.fromCharCodes(bytes.sublist(0, 4)), '%PDF');
    });

    test('generateVisitPdf with no data returns fallback page', () async {
      final bytes = await PdfGenerator.generateVisitPdf(visit: visit);
      expect(bytes.length, greaterThan(100));
      expect(String.fromCharCodes(bytes.sublist(0, 4)), '%PDF');
    });

    test('generateVisitPdf with SOAP note returns PDF bytes', () async {
      final soapNote = SoapNote(
        id: 1,
        visitId: 1,
        subjective: 'Patient reports pain in lower right.',
        objectiveClinical: 'Caries on #30 distal.',
        objectiveRadiographic: 'Periapical lucency #30.',
        objectiveVitals: null,
        assessment: 'Irreversible pulpitis #30.',
        planToday: jsonEncode(['Root canal #30']),
        planNextVisit: jsonEncode(['Crown prep #30']),
        planInstructions: jsonEncode(['Avoid chewing on right side']),
        cdtCodes: jsonEncode(['D3330']),
        medicationChanges: jsonEncode([
          {
            'drug_name': 'ibuprofen',
            'dose': '600mg',
            'frequency': 'TID×3 days',
            'change_type': 'prescribed',
            'prescribing_note': 'for pain',
          },
        ]),
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      final bytes = await PdfGenerator.generateVisitPdf(
        visit: visit,
        soapNote: soapNote,
      );
      expect(bytes.length, greaterThan(500));
      expect(String.fromCharCodes(bytes.sublist(0, 4)), '%PDF');
    });
  });
}
