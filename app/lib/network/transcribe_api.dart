import 'dart:io';

import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'api_client.dart';

part 'transcribe_api.g.dart';

@riverpod
Future<TranscribeApi> transcribeApi(TranscribeApiRef ref) async {
  final client = await ref.watch(apiClientProvider.future);
  return TranscribeApi(client.dio);
}

class TranscribeApi {
  const TranscribeApi(this._dio);
  final Dio _dio;

  Future<TranscribeResult> transcribe(
    File audioFile, {
    String language = 'en',
    String prompt = '',
  }) async {
    final formData = FormData.fromMap({
      'audio_file': await MultipartFile.fromFile(
        audioFile.path,
        filename: audioFile.path.split('/').last,
      ),
      'language': language,
      'prompt': prompt,
    });

    final response = await _dio.post<Map<String, dynamic>>(
      '/transcribe',
      data: formData,
    );

    final body = response.data!;
    return TranscribeResult(
      transcript: body['transcript'] as String,
      durationSeconds: (body['duration_seconds'] as num).toDouble(),
      language: body['language'] as String,
    );
  }
}

class TranscribeResult {
  const TranscribeResult({
    required this.transcript,
    required this.durationSeconds,
    required this.language,
  });

  final String transcript;
  final double durationSeconds;
  final String language;
}
