import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../data/database/app_database.dart';
import '../../shared/widgets/audio_recorder_button.dart';
import '../../shared/widgets/loading_overlay.dart';
import 'perio_chart_notifier.dart';

class PerioChartScreen extends ConsumerWidget {
  const PerioChartScreen({super.key, required this.visitId});

  final String visitId;

  int get _visitId => int.parse(visitId);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final voiceState = ref.watch(voicePerioNotifierProvider(_visitId));
    final voiceNotifier =
        ref.read(voicePerioNotifierProvider(_visitId).notifier);
    final chartAsync = ref.watch(perioChartForVisitProvider(_visitId));

    return LoadingOverlay(
      isLoading: voiceState.isProcessing,
      message: 'Processing perio readings…',
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Perio Chart'),
          actions: [
            chartAsync.when(
              data: (chart) => chart != null
                  ? _AapBadge(
                      stage: chart.aapStage ?? '—',
                      grade: chart.aapGrade ?? '—',
                      bopPct: chart.bopPercent ?? 0,
                    )
                  : const SizedBox.shrink(),
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
            ),
            const SizedBox(width: 12),
          ],
        ),
        body: Column(
          children: [
            if (voiceState.error != null)
              MaterialBanner(
                content: Text(voiceState.error!),
                actions: [
                  TextButton(
                    onPressed: voiceNotifier.clearError,
                    child: const Text('Dismiss'),
                  ),
                ],
              ),
            if (voiceState.lastParsedCount > 0)
              Padding(
                padding: const EdgeInsets.all(8),
                child: Text(
                  '${voiceState.lastParsedCount} readings parsed',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ),
            Expanded(child: _ChartBody(visitId: _visitId)),
          ],
        ),
        floatingActionButton: AudioRecorderButton(
          onRecordingComplete: (file) => voiceNotifier.processRecording(file),
          onError: (e) => ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(e.toString())),
          ),
        ),
        floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      ),
    );
  }
}

class _ChartBody extends ConsumerWidget {
  const _ChartBody({required this.visitId});
  final int visitId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chartAsync = ref.watch(perioChartForVisitProvider(visitId));

    return chartAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (chart) {
        if (chart == null) {
          return const Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              spacing: 12,
              children: [
                Icon(Icons.mic_none, size: 64, color: Colors.grey),
                Text(
                  'Record periodontal readings\nusing the microphone button.',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          );
        }
        return _LivePerioGrid(chartId: chart.id);
      },
    );
  }
}

class _LivePerioGrid extends ConsumerWidget {
  const _LivePerioGrid({required this.chartId});
  final int chartId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final readingsAsync = ref.watch(perioReadingsProvider(chartId));

    return readingsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (rows) {
        // Group into map by (tooth, surface)
        final readings = <(int, String), PerioReading>{};
        for (final r in rows) {
          readings[(r.toothNumber, r.surface)] = r;
        }
        return SingleChildScrollView(
          child: _PerioGrid(readings: readings),
        );
      },
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
        Text(
          'Stage $stage / Grade $grade',
          style: Theme.of(context)
              .textTheme
              .labelMedium
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
        Text(
          'BOP ${(bopPct * 100).toStringAsFixed(0)}%',
          style: Theme.of(context).textTheme.labelSmall,
        ),
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
          _ToothRow(
            teeth: ToothNumbering.upper,
            surface: 'buccal',
            readings: readings,
            label: 'B',
          ),
          _ToothRow(
            teeth: ToothNumbering.upper,
            surface: 'lingual',
            readings: readings,
            label: 'L',
          ),
          const Divider(thickness: 2),
          _ToothRow(
            teeth: ToothNumbering.lower,
            surface: 'lingual',
            readings: readings,
            label: 'L',
          ),
          _ToothRow(
            teeth: ToothNumbering.lower,
            surface: 'buccal',
            readings: readings,
            label: 'B',
          ),
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
        SizedBox(
          width: 24,
          child: Center(
            child: Text(label, style: const TextStyle(fontSize: 10)),
          ),
        ),
        for (final tooth in teeth)
          _ToothCell(
            tooth: tooth,
            surface: surface,
            reading: readings[(tooth, surface)],
          ),
      ],
    );
  }
}

class _ToothCell extends StatelessWidget {
  const _ToothCell({
    required this.tooth,
    required this.surface,
    this.reading,
  });

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
          Text('#$tooth',
              style: const TextStyle(fontSize: 9, color: Colors.grey),),
          if (depths.isEmpty)
            const Text('–  –  –',
                style: TextStyle(fontSize: 10, color: Colors.grey),)
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
                            style: const TextStyle(
                                fontSize: 9, color: Colors.white,),
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
