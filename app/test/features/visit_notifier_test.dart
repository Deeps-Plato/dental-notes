import 'dart:io';

import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/models/perio_chart.dart' as perio_models;
import 'package:dental_notes/data/models/soap_note.dart' as models;
import 'package:dental_notes/data/repositories/soap_note_repository.dart';
import 'package:dental_notes/data/repositories/visit_repository.dart';
import 'package:dental_notes/features/visit/visit_notifier.dart';
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
  models.SoapNote? soapResult;
  Exception? soapError;
  bool generateSoapCalled = false;

  @override
  Future<models.SoapNote> generateSoap(
    String transcript, {
    String? patientContext,
    int placeholderVisitId = 0,
  }) async {
    generateSoapCalled = true;
    if (soapError != null) throw soapError!;
    return soapResult!;
  }

  @override
  Future<List<perio_models.PerioReading>> parsePerio(String transcript) =>
      throw UnimplementedError();

  @override
  Future<List<models.MedicationChange>> extractMedications(
    String transcript,
  ) =>
      throw UnimplementedError();
}

// ── Helpers ──────────────────────────────────────────────────────────────────

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

models.SoapNote _sampleSoap({int visitId = 1}) => models.SoapNote(
      id: 0,
      visitId: visitId,
      subjective: 'Patient reports pain.',
      objectiveClinical: 'Caries #30.',
      assessment: 'Pulpitis.',
      planToday: ['Root canal'],
      planNextVisit: [],
      planInstructions: [],
      cdtCodes: ['D3330'],
      medicationChanges: [],
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );

({
  ProviderContainer container,
  FakeTranscribeApi transcribeApi,
  FakeNotesApi notesApi,
  AppDatabase db,
}) _setup() {
  final db = _openTestDb();
  final visitRepo = VisitRepository(db);
  final soapRepo = SoapNoteRepository(db);
  final fakeTranscribe = FakeTranscribeApi();
  final fakeNotes = FakeNotesApi();

  final container = ProviderContainer(
    overrides: [
      visitRepositoryProvider.overrideWithValue(visitRepo),
      soapNoteRepositoryProvider.overrideWithValue(soapRepo),
      transcribeApiProvider.overrideWith((ref) async => fakeTranscribe),
      notesApiProvider.overrideWith((ref) async => fakeNotes),
    ],
  );

  return (
    container: container,
    transcribeApi: fakeTranscribe,
    notesApi: fakeNotes,
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
  group('VisitNotifier', () {
    test('initial state is empty', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final state = s.container.read(visitNotifierProvider(1));
      expect(state.transcript, isNull);
      expect(state.soapNote, isNull);
      expect(state.isRecording, false);
      expect(state.isTranscribing, false);
      expect(state.isGeneratingNote, false);
      expect(state.error, isNull);
    });

    test('transcribeAudio success sets transcript', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();

      s.transcribeApi.result = const TranscribeResult(
        transcript: 'Patient says tooth hurts.',
        durationSeconds: 5.0,
        language: 'en',
      );

      final notifier =
          s.container.read(visitNotifierProvider(1).notifier);
      await notifier.transcribeAudio(mockFile);

      final state = s.container.read(visitNotifierProvider(1));
      expect(state.transcript, 'Patient says tooth hurts.');
      expect(state.isTranscribing, false);
      expect(state.error, isNull);
    });

    test('transcribeAudio failure sets error', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();

      s.transcribeApi.error = Exception('Network error');

      final notifier =
          s.container.read(visitNotifierProvider(1).notifier);
      await notifier.transcribeAudio(mockFile);

      final state = s.container.read(visitNotifierProvider(1));
      expect(state.transcript, isNull);
      expect(state.isTranscribing, false);
      expect(state.error, contains('Transcription failed'));
    });

    test('transcribeAudio deletes audio file even on failure', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();

      s.transcribeApi.error = Exception('fail');

      final notifier =
          s.container.read(visitNotifierProvider(1).notifier);
      await notifier.transcribeAudio(mockFile);

      expect(mockFile.deleted, true);
    });

    test('generateSoapNote does nothing without transcript', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final notifier =
          s.container.read(visitNotifierProvider(1).notifier);
      await notifier.generateSoapNote();

      final state = s.container.read(visitNotifierProvider(1));
      expect(state.isGeneratingNote, false);
      expect(state.soapNote, isNull);
      expect(s.notesApi.generateSoapCalled, false);
    });

    test('generateSoapNote success sets soapNote with DB id', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      // First transcribe to set transcript.
      final mockFile = FakeFile();
      s.transcribeApi.result = const TranscribeResult(
        transcript: 'Tooth hurts',
        durationSeconds: 3.0,
        language: 'en',
      );

      final notifier =
          s.container.read(visitNotifierProvider(1).notifier);
      await notifier.transcribeAudio(mockFile);

      // Now generate SOAP note.
      s.notesApi.soapResult = _sampleSoap();
      await notifier.generateSoapNote();

      final state = s.container.read(visitNotifierProvider(1));
      expect(state.soapNote, isNotNull);
      expect(state.soapNote!.id, greaterThan(0)); // real DB id
      expect(state.soapNote!.subjective, 'Patient reports pain.');
      expect(state.isGeneratingNote, false);
      expect(state.error, isNull);
    });

    test('generateSoapNote failure sets error', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      // Set transcript.
      final mockFile = FakeFile();
      s.transcribeApi.result = const TranscribeResult(
        transcript: 'text',
        durationSeconds: 1.0,
        language: 'en',
      );

      final notifier =
          s.container.read(visitNotifierProvider(1).notifier);
      await notifier.transcribeAudio(mockFile);

      // Fail SOAP generation.
      s.notesApi.soapError = Exception('Claude API error');
      await notifier.generateSoapNote();

      final state = s.container.read(visitNotifierProvider(1));
      expect(state.soapNote, isNull);
      expect(state.isGeneratingNote, false);
      expect(state.error, contains('Note generation failed'));
    });

    test('clearError resets error to null', () async {
      final s = _setup();
      addTearDown(() {
        s.container.dispose();
        s.db.close();
      });
      await _insertPatientAndVisit(s.db);

      final mockFile = FakeFile();
      s.transcribeApi.error = Exception('fail');

      final notifier =
          s.container.read(visitNotifierProvider(1).notifier);
      await notifier.transcribeAudio(mockFile);

      expect(s.container.read(visitNotifierProvider(1)).error, isNotNull);

      notifier.clearError();
      expect(s.container.read(visitNotifierProvider(1)).error, isNull);
    });
  });
}
