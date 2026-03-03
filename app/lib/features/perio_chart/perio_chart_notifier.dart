import 'dart:io';

import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/database/app_database.dart';
import '../../data/models/perio_chart.dart' as models;
import '../../data/repositories/perio_repository.dart';
import '../../network/notes_api.dart';
import '../../network/transcribe_api.dart';

part 'perio_chart_notifier.g.dart';

/// Watch the perio chart for a visit.
@riverpod
Stream<PerioChart?> perioChartForVisit(PerioChartForVisitRef ref, int visitId) {
  final repo = ref.watch(perioRepositoryProvider);
  return repo.watchChartForVisit(visitId);
}

/// Watch all readings for a chart.
@riverpod
Stream<List<PerioReading>> perioReadings(PerioReadingsRef ref, int chartId) {
  final repo = ref.watch(perioRepositoryProvider);
  return repo.watchReadingsForChart(chartId);
}

/// State for the voice perio entry flow.
class VoicePerioState {
  const VoicePerioState({
    this.isProcessing = false,
    this.lastParsedCount = 0,
    this.error,
  });

  final bool isProcessing;
  final int lastParsedCount;
  final String? error;

  VoicePerioState copyWith({
    bool? isProcessing,
    int? lastParsedCount,
    String? error,
    bool clearError = false,
  }) => VoicePerioState(
    isProcessing: isProcessing ?? this.isProcessing,
    lastParsedCount: lastParsedCount ?? this.lastParsedCount,
    error: clearError ? null : (error ?? this.error),
  );
}

/// Manages voice → transcribe → parse → save perio readings.
@riverpod
class VoicePerioNotifier extends _$VoicePerioNotifier {
  @override
  VoicePerioState build(int visitId) => const VoicePerioState();

  /// Record → transcribe → parse → save readings.
  Future<void> processRecording(File audioFile) async {
    state = state.copyWith(isProcessing: true, clearError: true);
    try {
      // Transcribe
      final transcribeApi = await ref.read(transcribeApiProvider.future);
      final result = await transcribeApi.transcribe(
        audioFile,
        prompt: 'Periodontal probing depths. Tooth number, surface, three depths.',
      );

      // Parse via Claude
      final notesApi = await ref.read(notesApiProvider.future);
      final readings = await notesApi.parsePerio(result.transcript);

      // Ensure chart exists and save
      final repo = ref.read(perioRepositoryProvider);
      final chartId = await repo.ensureChart(visitId);
      await repo.saveReadings(chartId: chartId, readings: readings);

      state = state.copyWith(
        isProcessing: false,
        lastParsedCount: readings.length,
      );
    } catch (e) {
      state = state.copyWith(
        isProcessing: false,
        error: 'Perio parse failed: $e',
      );
    } finally {
      try {
        await audioFile.delete();
      } catch (_) {}
    }
  }

  /// Manually save a single reading (tap entry fallback).
  Future<void> saveManualReading(models.PerioReading reading) async {
    try {
      final repo = ref.read(perioRepositoryProvider);
      final chartId = await repo.ensureChart(visitId);
      await repo.saveReading(chartId: chartId, reading: reading);
    } catch (e) {
      state = state.copyWith(error: 'Save failed: $e');
    }
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }
}
