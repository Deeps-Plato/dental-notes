import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../shared/widgets/audio_recorder_button.dart';
import '../../shared/widgets/loading_overlay.dart';
import 'visit_notifier.dart';

class VisitScreen extends ConsumerWidget {
  const VisitScreen({super.key, required this.patientId, required this.visitId});

  final String patientId;
  final String visitId;

  int get _visitId => int.parse(visitId);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(visitNotifierProvider(_visitId));
    final notifier = ref.read(visitNotifierProvider(_visitId).notifier);
    final isLoading = state.isTranscribing || state.isGeneratingNote;
    final loadingMessage = state.isTranscribing
        ? 'Transcribing…'
        : state.isGeneratingNote
            ? 'Generating SOAP note…'
            : null;

    return LoadingOverlay(
      isLoading: isLoading,
      message: loadingMessage,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Visit'),
          actions: [
            if (state.transcript != null && state.soapNote == null)
              FilledButton.tonal(
                onPressed: state.isGeneratingNote
                    ? null
                    : () => notifier.generateSoapNote(),
                child: const Text('Generate Note'),
              ),
            if (state.soapNote != null)
              TextButton(
                onPressed: () => context.go(
                  '/patients/$patientId/visit/$visitId/soap',
                ),
                child: const Text('View Note'),
              ),
            const SizedBox(width: 8),
          ],
        ),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: 16,
            children: [
              _VisitNav(patientId: patientId, visitId: visitId),
              if (state.error != null)
                Card(
                  color: Theme.of(context).colorScheme.errorContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            state.error!,
                            style: TextStyle(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onErrorContainer,
                            ),
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close, size: 18),
                          onPressed: notifier.clearError,
                        ),
                      ],
                    ),
                  ),
                ),
              Expanded(
                child: state.transcript != null
                    ? _TranscriptCard(transcript: state.transcript!)
                    : const _RecordingPrompt(),
              ),
            ],
          ),
        ),
        floatingActionButton: AudioRecorderButton(
          onRecordingComplete: (file) => notifier.transcribeAudio(file),
          onError: (e) => ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(e.toString())),
          ),
        ),
        floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      ),
    );
  }
}

class _VisitNav extends StatelessWidget {
  const _VisitNav({required this.patientId, required this.visitId});
  final String patientId;
  final String visitId;

  @override
  Widget build(BuildContext context) {
    final base = '/patients/$patientId/visit/$visitId';
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        spacing: 8,
        children: [
          _NavChip(
            label: 'Recording',
            icon: Icons.mic,
            isActive: true,
            onTap: () {},
          ),
          _NavChip(
            label: 'SOAP Note',
            icon: Icons.description_outlined,
            onTap: () => context.go('$base/soap'),
          ),
          _NavChip(
            label: 'Perio Chart',
            icon: Icons.grid_on,
            onTap: () => context.go('$base/perio'),
          ),
          _NavChip(
            label: 'Odontogram',
            icon: Icons.brush_outlined,
            onTap: () => context.go('$base/odontogram'),
          ),
          _NavChip(
            label: 'Export PDF',
            icon: Icons.picture_as_pdf,
            onTap: () => context.go('$base/pdf'),
          ),
        ],
      ),
    );
  }
}

class _NavChip extends StatelessWidget {
  const _NavChip({
    required this.label,
    required this.icon,
    required this.onTap,
    this.isActive = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback onTap;
  final bool isActive;

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      label: Row(
        mainAxisSize: MainAxisSize.min,
        spacing: 4,
        children: [Icon(icon, size: 16), Text(label)],
      ),
      selected: isActive,
      onSelected: (_) => onTap(),
    );
  }
}

class _RecordingPrompt extends StatelessWidget {
  const _RecordingPrompt();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        spacing: 12,
        children: [
          Icon(Icons.mic_none,
              size: 72, color: Theme.of(context).colorScheme.primary,),
          Text(
            'Tap the microphone to begin recording',
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          Text(
            'Audio is transcribed and deleted immediately.\n'
            'Nothing is stored on the server.',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _TranscriptCard extends StatelessWidget {
  const _TranscriptCard({required this.transcript});

  final String transcript;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('Transcript',
                    style: Theme.of(context).textTheme.titleSmall,),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.copy, size: 18),
                  tooltip: 'Copy',
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: transcript));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Copied to clipboard')),
                    );
                  },
                ),
              ],
            ),
            const Divider(),
            Expanded(
              child: SingleChildScrollView(child: Text(transcript)),
            ),
          ],
        ),
      ),
    );
  }
}
