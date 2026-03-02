import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../data/models/perio_chart.dart';
import '../../domain/perio_logic.dart';
import '../../network/notes_api.dart';
import '../../network/transcribe_api.dart';
import '../../shared/widgets/audio_recorder_button.dart';
import '../../shared/widgets/loading_overlay.dart';

class PerioChartScreen extends ConsumerStatefulWidget {
  const PerioChartScreen({super.key, required this.visitId});

  final String visitId;

  @override
  ConsumerState<PerioChartScreen> createState() => _PerioChartScreenState();
}

class _PerioChartScreenState extends ConsumerState<PerioChartScreen> {
  // Map from (toothNumber, surface) → PerioReading
  final Map<(int, String), PerioReading> _readings = {};
  bool _isProcessing = false;
  String? _error;

  Future<void> _handleVoiceRecording(File audio) async {
    setState(() {
      _isProcessing = true;
      _error = null;
    });
    try {
      final transcribeApi = await ref.read(transcribeApiProvider.future);
      final result = await transcribeApi.transcribe(audio, prompt: 'Periodontal probing.');

      final notesApi = await ref.read(notesApiProvider.future);
      final parsed = await notesApi.parsePerio(result.transcript);

      setState(() {
        for (final r in parsed) {
          _readings[(r.toothNumber, r.surface)] = r;
        }
      });
    } catch (e) {
      setState(() => _error = 'Failed: $e');
    } finally {
      try {
        await audio.delete();
      } catch (_) {}
      setState(() => _isProcessing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final allReadings = _readings.values.toList();
    final stage = allReadings.isEmpty ? '—' : PerioLogic.calculateStage(allReadings);
    final grade = allReadings.isEmpty ? '—' : PerioLogic.calculateGrade(allReadings);
    final bopPct = PerioLogic.calculateBopPercent(allReadings);

    return LoadingOverlay(
      isLoading: _isProcessing,
      message: 'Processing perio readings…',
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Perio Chart'),
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: _AapBadge(stage: stage, grade: grade, bopPct: bopPct),
            ),
          ],
        ),
        body: Column(
          children: [
            if (_error != null)
              MaterialBanner(
                content: Text(_error!),
                actions: [TextButton(onPressed: () => setState(() => _error = null), child: const Text('Dismiss'))],
              ),
            Expanded(
              child: SingleChildScrollView(
                child: _PerioGrid(readings: _readings),
              ),
            ),
          ],
        ),
        floatingActionButton: AudioRecorderButton(
          onRecordingComplete: _handleVoiceRecording,
          onError: (e) => setState(() => _error = e.toString()),
        ),
        floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      ),
    );
  }
}

class _AapBadge extends StatelessWidget {
  const _AapBadge({
    required this.stage,
    required this.grade,
    required this.bopPct,
  });

  final String stage;
  final String grade;
  final double bopPct;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text('Stage $stage / Grade $grade',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(fontWeight: FontWeight.bold)),
        Text('BOP ${(bopPct * 100).toStringAsFixed(0)}%',
            style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}

/// Renders a compact grid: 32 teeth columns, buccal/lingual rows.
class _PerioGrid extends StatelessWidget {
  const _PerioGrid({required this.readings});

  final Map<(int, String), PerioReading> readings;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Column(
        children: [
          _ToothRow(teeth: ToothNumbering.upper, surface: 'buccal', readings: readings, label: 'B'),
          _ToothRow(teeth: ToothNumbering.upper, surface: 'lingual', readings: readings, label: 'L'),
          const Divider(thickness: 2),
          _ToothRow(teeth: ToothNumbering.lower, surface: 'lingual', readings: readings, label: 'L'),
          _ToothRow(teeth: ToothNumbering.lower, surface: 'buccal', readings: readings, label: 'B'),
        ],
      ),
    );
  }
}

class _ToothRow extends StatelessWidget {
  const _ToothRow({
    required this.teeth,
    required this.surface,
    required this.readings,
    required this.label,
  });

  final List<int> teeth;
  final String surface;
  final Map<(int, String), PerioReading> readings;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(width: 24, child: Center(child: Text(label, style: const TextStyle(fontSize: 10)))),
        for (final tooth in teeth) _ToothCell(tooth: tooth, surface: surface, reading: readings[(tooth, surface)]),
      ],
    );
  }
}

class _ToothCell extends StatelessWidget {
  const _ToothCell({required this.tooth, required this.surface, this.reading});

  final int tooth;
  final String surface;
  final PerioReading? reading;

  @override
  Widget build(BuildContext context) {
    final depths = reading != null
        ? [reading!.depthMb, reading!.depthB, reading!.depthDb]
        : <int>[];

    return Container(
      width: 48,
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('#$tooth', style: const TextStyle(fontSize: 9, color: Colors.grey)),
          if (depths.isEmpty)
            const Text('–  –  –', style: TextStyle(fontSize: 10, color: Colors.grey))
          else
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: depths
                  .map(
                    (d) => Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 1),
                      child: Container(
                        width: 14,
                        height: 14,
                        decoration: BoxDecoration(
                          color: PerioColors.forDepth(d),
                          shape: BoxShape.circle,
                        ),
                        child: Center(
                          child: Text(
                            '$d',
                            style: const TextStyle(fontSize: 9, color: Colors.white),
                          ),
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
          if (reading?.bop == true)
            Container(
              width: 6,
              height: 6,
              decoration: const BoxDecoration(
                color: PerioColors.bop,
                shape: BoxShape.circle,
              ),
            ),
        ],
      ),
    );
  }
}
