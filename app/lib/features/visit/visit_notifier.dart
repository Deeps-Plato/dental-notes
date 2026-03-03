import 'dart:io';

import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/database/app_database.dart';
import '../../data/models/soap_note.dart' as models;
import '../../data/repositories/soap_note_repository.dart';
import '../../data/repositories/visit_repository.dart';
import '../../network/notes_api.dart';
import '../../network/transcribe_api.dart';

part 'visit_notifier.g.dart';

/// State for an active visit session.
class VisitState {
  const VisitState({
    this.transcript,
    this.soapNote,
    this.isRecording = false,
    this.isTranscribing = false,
    this.isGeneratingNote = false,
    this.error,
  });

  final String? transcript;
  final models.SoapNote? soapNote;
  final bool isRecording;
  final bool isTranscribing;
  final bool isGeneratingNote;
  final String? error;

  VisitState copyWith({
    String? transcript,
    models.SoapNote? soapNote,
    bool? isRecording,
    bool? isTranscribing,
    bool? isGeneratingNote,
    String? error,
    bool clearError = false,
  }) => VisitState(
    transcript: transcript ?? this.transcript,
    soapNote: soapNote ?? this.soapNote,
    isRecording: isRecording ?? this.isRecording,
    isTranscribing: isTranscribing ?? this.isTranscribing,
    isGeneratingNote: isGeneratingNote ?? this.isGeneratingNote,
    error: clearError ? null : (error ?? this.error),
  );
}

@riverpod
class VisitNotifier extends _$VisitNotifier {
  @override
  VisitState build(int visitId) => const VisitState();

  /// Record → transcribe → store transcript.
  Future<void> transcribeAudio(File audioFile) async {
    state = state.copyWith(isTranscribing: true, clearError: true);
    try {
      final api = await ref.read(transcribeApiProvider.future);
      final result = await api.transcribe(audioFile);

      // Persist transcript to DB
      final visitRepo = ref.read(visitRepositoryProvider);
      await visitRepo.saveTranscript(visitId, result.transcript);

      state = state.copyWith(
        transcript: result.transcript,
        isTranscribing: false,
      );
    } catch (e) {
      state = state.copyWith(
        isTranscribing: false,
        error: 'Transcription failed: $e',
      );
    } finally {
      // Delete local audio immediately — no PHI on filesystem
      try {
        await audioFile.delete();
      } catch (_) {}
    }
  }

  /// Transcript → generate SOAP note via Claude.
  Future<void> generateSoapNote({String? patientContext}) async {
    final transcript = state.transcript;
    if (transcript == null || transcript.isEmpty) return;

    state = state.copyWith(isGeneratingNote: true, clearError: true);
    try {
      final api = await ref.read(notesApiProvider.future);
      final note = await api.generateSoap(
        transcript,
        patientContext: patientContext,
        placeholderVisitId: visitId,
      );

      // Persist to DB
      final noteRepo = ref.read(soapNoteRepositoryProvider);
      await noteRepo.save(visitId: visitId, note: note);

      state = state.copyWith(
        soapNote: note,
        isGeneratingNote: false,
      );
    } catch (e) {
      state = state.copyWith(
        isGeneratingNote: false,
        error: 'Note generation failed: $e',
      );
    }
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }
}

/// Watch visits for a patient.
@riverpod
Stream<List<Visit>> visitList(VisitListRef ref, int patientId) {
  final repo = ref.watch(visitRepositoryProvider);
  return repo.watchForPatient(patientId);
}
