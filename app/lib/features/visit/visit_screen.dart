import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../network/transcribe_api.dart';
import '../../shared/widgets/audio_recorder_button.dart';
import '../../shared/widgets/loading_overlay.dart';

class VisitScreen extends ConsumerStatefulWidget {
  const VisitScreen({super.key, required this.patientId, required this.visitId});

  final String patientId;
  final String visitId;

  @override
  ConsumerState<VisitScreen> createState() => _VisitScreenState();
}

class _VisitScreenState extends ConsumerState<VisitScreen> {
  String? _transcript;
  bool _isTranscribing = false;
  String? _errorMessage;

  Future<void> _handleRecordingComplete(File audioFile) async {
    setState(() {
      _isTranscribing = true;
      _errorMessage = null;
    });
    try {
      final api = await ref.read(transcribeApiProvider.future);
      final result = await api.transcribe(audioFile);
      setState(() => _transcript = result.transcript);
    } catch (e) {
      setState(() => _errorMessage = 'Transcription failed: $e');
    } finally {
      // Delete local audio file immediately — no PHI on device filesystem
      try {
        await audioFile.delete();
      } catch (_) {}
      setState(() => _isTranscribing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return LoadingOverlay(
      isLoading: _isTranscribing,
      message: 'Transcribing…',
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Visit'),
          actions: [
            if (_transcript != null)
              TextButton(
                onPressed: () => context.go(
                  '/patients/${widget.patientId}/visit/${widget.visitId}/soap',
                ),
                child: const Text('Generate Note'),
              ),
          ],
        ),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: 16,
            children: [
              const _VisitNav(),
              if (_errorMessage != null)
                Card(
                  color: Theme.of(context).colorScheme.errorContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      _errorMessage!,
                      style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer),
                    ),
                  ),
                ),
              Expanded(
                child: _transcript != null
                    ? _TranscriptCard(transcript: _transcript!)
                    : const _RecordingPrompt(),
              ),
            ],
          ),
        ),
        floatingActionButton: AudioRecorderButton(
          onRecordingComplete: _handleRecordingComplete,
          onError: (e) => setState(() => _errorMessage = e.toString()),
        ),
        floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      ),
    );
  }
}

class _VisitNav extends StatelessWidget {
  const _VisitNav();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        spacing: 8,
        children: [
          _NavChip(label: 'Recording', icon: Icons.mic, isActive: true, onTap: () {}),
          _NavChip(label: 'SOAP Note', icon: Icons.description_outlined, onTap: () {}),
          _NavChip(label: 'Perio Chart', icon: Icons.grid_on, onTap: () {}),
          _NavChip(label: 'Odontogram', icon: Icons.brush_outlined, onTap: () {}),
          _NavChip(label: 'Export PDF', icon: Icons.picture_as_pdf, onTap: () {}),
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
          Icon(Icons.mic_none, size: 72, color: Theme.of(context).colorScheme.primary),
          Text(
            'Tap the microphone to begin recording',
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          Text(
            'Audio is transcribed and deleted immediately.\nNothing is stored on the server.',
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
                Text('Transcript', style: Theme.of(context).textTheme.titleSmall),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.copy, size: 18),
                  tooltip: 'Copy',
                  onPressed: () {
                    // TODO: clipboard
                  },
                ),
              ],
            ),
            const Divider(),
            Expanded(
              child: SingleChildScrollView(
                child: Text(transcript),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
