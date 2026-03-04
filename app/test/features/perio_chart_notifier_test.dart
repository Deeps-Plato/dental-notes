import 'dart:io';

import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/models/perio_chart.dart' as models;
import 'package:dental_notes/data/models/soap_note.dart' as soap_models;
import 'package:dental_notes/data/repositories/perio_repository.dart';
import 'package:dental_notes/features/perio_chart/perio_chart_notifier.dart';
import 'package:dental_notes/network/notes_api.dart';
import 'package:dental_notes/network/transcribe_api.dart';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

// ── Fakes ────────────────────────────────────────────────────────────────────

class FakeFile extends Fake implements File {
  bool deleted = false;

  @override
  Future<FileSystemEntity> delete({bool recursive = false}) async {
    deleted = true;
    return this;
  }
}

class FakeTranscribeApi implements TranscribeApi {
  TranscribeResult? result;
  Exception? error;

  @override
  Future<TranscribeResult> transcribe(
    File audioFile, {
    String language = 'en',
    String prompt = '',
  }) async {
    if (error != null) throw error!;
    return result!;
  }
}

class FakeNotesApi implements NotesApi {
  List<models.PerioReading>? perioResult;
  Exception? perioError;

  @override
  Future<List<models.PerioReading>> parsePerio(String transcript) async {
    if (perioError != null) throw perioError!;
    return perioResult!;
  }

  @override
  Future<soap_models.SoapNote> generateSoap(
    String transcript, {
    String? patientContext,
    int placeholderVisitId = 0,
  }) =>
      throw UnimplementedError();

  @override
  Future<List<soap_models.MedicationChange>> extractMedications(
    String transcript,
  ) =>
      throw UnimplementedError();
}


// ── Helpers ──────────────────────────────────────────────────────────────────

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

({
  ProviderContainer container,
  FakeTranscribeApi transcribeApi,
  FakeNotesApi notesApi,
  PerioRepository perioRepo,
  AppDatabase db,
}) _setup() {
  final db = _openTestDb();
  final perioRepo = PerioRepository(db);
  final fakeTranscribe = FakeTranscribeApi();
  final fakeNotes = FakeNotesApi();

  final container = ProviderContainer(
    overrides: [
      perioRepositoryProvider.overrideWithValue(perioRepo),
      transcribeApiProvider.overrideWith((ref) async => fakeTranscribe),
      notesApiProvider.overrideWith((ref) async => fakeNotes),
    ],
  );

  return (
    container: container,
    transcribeApi: fakeTranscribe,
    notesApi: fakeNotes,
    perioRepo: perioRepo,
    db: db,
  );
}

Future<void> _insertPatientAndVisit(AppDatabase db) async {
  await db.into(db.patients).insert(PatientsCompanion.insert(
        firstName: 'T',
        lastName: 'P',
        dateOfBirth: DateTime(1990, 1, 1),
      ),);
  await db.into(db.visits).insert(VisitsCompanion.insert(
        patientId: 1,
        visitDate: DateTime(2024, 6, 15),
      ),);
}

void main() {
  group('VoicePerioNotifier', () {
    test('initial state is idle', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final state = s.container.read(voicePerioNotifierProvider(1));
      expect(state.isProcessing, false);
      expect(state.lastParsedCount, 0);
      expect(state.error, isNull);
    });

    test('processRecording success saves readings and updates count',
        () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();

      s.transcribeApi.result = const TranscribeResult(
        transcript: 'Tooth 14 buccal 3 2 4 BOP',
        durationSeconds: 4.0,
        language: 'en',
      );
      s.notesApi.perioResult = const [
        models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'buccal',
          depthMb: 3,
          depthB: 2,
          depthDb: 4,
          bop: true,
          recession: 0,
        ),
      ];

      final notifier =
          s.container.read(voicePerioNotifierProvider(1).notifier);
      await notifier.processRecording(mockFile);

      final state = s.container.read(voicePerioNotifierProvider(1));
      expect(state.isProcessing, false);
      expect(state.lastParsedCount, 1);
      expect(state.error, isNull);

      // Verify data was saved to DB.
      final chartId = await s.perioRepo.ensureChart(1);
      final readings = await s.perioRepo.getReadingsForChart(chartId);
      expect(readings.length, 1);
      expect(readings.first.toothNumber, 14);
    });

    test('processRecording failure sets error', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();

      s.transcribeApi.error = Exception('Microphone error');

      final notifier =
          s.container.read(voicePerioNotifierProvider(1).notifier);
      await notifier.processRecording(mockFile);

      final state = s.container.read(voicePerioNotifierProvider(1));
      expect(state.isProcessing, false);
      expect(state.error, contains('Perio parse failed'));
    });

    test('processRecording deletes audio file on success', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();

      s.transcribeApi.result = const TranscribeResult(
        transcript: 'text',
        durationSeconds: 1.0,
        language: 'en',
      );
      s.notesApi.perioResult = [];

      final notifier =
          s.container.read(voicePerioNotifierProvider(1).notifier);
      await notifier.processRecording(mockFile);

      expect(mockFile.deleted, true);
    });

    test('processRecording deletes audio file on failure', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();

      s.transcribeApi.error = Exception('fail');

      final notifier =
          s.container.read(voicePerioNotifierProvider(1).notifier);
      await notifier.processRecording(mockFile);

      expect(mockFile.deleted, true);
    });

    test('saveManualReading saves to DB', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final notifier =
          s.container.read(voicePerioNotifierProvider(1).notifier);
      await notifier.saveManualReading(const models.PerioReading(
        id: 0,
        chartId: 0,
        toothNumber: 19,
        surface: 'lingual',
        depthMb: 5,
        depthB: 4,
        depthDb: 6,
        bop: true,
        recession: 2,
      ),);

      // Verify persisted.
      final chartId = await s.perioRepo.ensureChart(1);
      final readings = await s.perioRepo.getReadingsForChart(chartId);
      expect(readings.length, 1);
      expect(readings.first.toothNumber, 19);
      expect(readings.first.depthMb, 5);
    });

    test('clearError resets error to null', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();
      s.transcribeApi.error = Exception('err');

      final notifier =
          s.container.read(voicePerioNotifierProvider(1).notifier);
      await notifier.processRecording(mockFile);
      expect(
        s.container.read(voicePerioNotifierProvider(1)).error,
        isNotNull,
      );

      notifier.clearError();
      expect(
        s.container.read(voicePerioNotifierProvider(1)).error,
        isNull,
      );
    });
  });
}
