import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

/// A button that toggles audio recording.
///
/// When recording stops, [onRecordingComplete] is called with the resulting
/// audio [File].  Callers are responsible for deleting the file after use.
class AudioRecorderButton extends StatefulWidget {
  const AudioRecorderButton({
    super.key,
    required this.onRecordingComplete,
    this.onError,
  });

  final void Function(File audioFile) onRecordingComplete;
  final void Function(Object error)? onError;

  @override
  State<AudioRecorderButton> createState() => _AudioRecorderButtonState();
}

class _AudioRecorderButtonState extends State<AudioRecorderButton> {
  final _recorder = AudioRecorder();
  bool _isRecording = false;

  @override
  void dispose() {
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    if (_isRecording) {
      await _stop();
    } else {
      await _start();
    }
  }

  Future<void> _start() async {
    try {
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        widget.onError?.call(
          Exception('Microphone permission denied'),
        );
        return;
      }

      final dir = await getTemporaryDirectory();
      final path =
          '${dir.path}/recording_${DateTime.now().millisecondsSinceEpoch}.m4a';

      await _recorder.start(
        const RecordConfig(encoder: AudioEncoder.aacLc, bitRate: 128000),
        path: path,
      );
      setState(() => _isRecording = true);
    } catch (e) {
      widget.onError?.call(e);
    }
  }

  Future<void> _stop() async {
    try {
      final path = await _recorder.stop();
      setState(() => _isRecording = false);
      if (path != null) {
        widget.onRecordingComplete(File(path));
      }
    } catch (e) {
      setState(() => _isRecording = false);
      widget.onError?.call(e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: _isRecording ? colorScheme.error : colorScheme.primary,
        boxShadow: _isRecording
            ? [BoxShadow(color: colorScheme.error.withOpacity(0.4), blurRadius: 16)]
            : null,
      ),
      child: IconButton(
        onPressed: _toggle,
        icon: Icon(
          _isRecording ? Icons.stop_rounded : Icons.mic_rounded,
          color: colorScheme.onPrimary,
          size: 32,
        ),
        tooltip: _isRecording ? 'Stop recording' : 'Start recording',
        padding: const EdgeInsets.all(20),
      ),
    );
  }
}
