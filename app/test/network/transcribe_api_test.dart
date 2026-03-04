import 'dart:io';

import 'package:dental_notes/network/transcribe_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Creates a Dio instance that intercepts all requests and returns
/// [responseData] as the response body.
Dio _mockDio(Map<String, dynamic> responseData) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test'));
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) {
      handler.resolve(Response(
        requestOptions: options,
        data: responseData,
        statusCode: 200,
      ),);
    },
  ),);
  return dio;
}

/// Creates a Dio that rejects requests with the given error.
Dio _errorDio(int statusCode, String message) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test'));
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) {
      handler.reject(DioException(
        requestOptions: options,
        response: Response(
          requestOptions: options,
          statusCode: statusCode,
          statusMessage: message,
        ),
        type: DioExceptionType.badResponse,
      ),);
    },
  ),);
  return dio;
}

void main() {
  late File tempFile;

  setUp(() {
    // Create a real temporary file for MultipartFile.fromFile.
    tempFile = File('${Directory.systemTemp.path}/test_audio.wav');
    tempFile.writeAsBytesSync([0, 1, 2, 3]); // minimal content
  });

  tearDown(() {
    if (tempFile.existsSync()) tempFile.deleteSync();
  });

  test('transcribe parses response correctly', () async {
    final dio = _mockDio({
      'transcript': 'Patient reports toothache on lower right.',
      'duration_seconds': 12.4,
      'language': 'en',
    });

    final api = TranscribeApi(dio);
    final result = await api.transcribe(tempFile);

    expect(result.transcript, 'Patient reports toothache on lower right.');
    expect(result.durationSeconds, 12.4);
    expect(result.language, 'en');
  });

  test('transcribe passes language parameter', () async {
    String? capturedLanguage;

    final dio = Dio(BaseOptions(baseUrl: 'http://test'));
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        // Capture form data fields.
        if (options.data is FormData) {
          final formData = options.data as FormData;
          capturedLanguage = formData.fields
              .firstWhere((e) => e.key == 'language')
              .value;
        }
        handler.resolve(Response(
          requestOptions: options,
          data: {
            'transcript': 'text',
            'duration_seconds': 1.0,
            'language': 'es',
          },
          statusCode: 200,
        ),);
      },
    ),);

    final api = TranscribeApi(dio);
    await api.transcribe(tempFile, language: 'es');

    expect(capturedLanguage, 'es');
  });

  test('transcribe passes prompt parameter', () async {
    String? capturedPrompt;

    final dio = Dio(BaseOptions(baseUrl: 'http://test'));
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (options.data is FormData) {
          final formData = options.data as FormData;
          capturedPrompt = formData.fields
              .firstWhere((e) => e.key == 'prompt')
              .value;
        }
        handler.resolve(Response(
          requestOptions: options,
          data: {
            'transcript': 'text',
            'duration_seconds': 1.0,
            'language': 'en',
          },
          statusCode: 200,
        ),);
      },
    ),);

    final api = TranscribeApi(dio);
    await api.transcribe(tempFile, prompt: 'dental vocabulary');

    expect(capturedPrompt, 'dental vocabulary');
  });

  test('transcribe handles integer duration_seconds', () async {
    final dio = _mockDio({
      'transcript': 'short',
      'duration_seconds': 5,
      'language': 'en',
    });

    final api = TranscribeApi(dio);
    final result = await api.transcribe(tempFile);

    expect(result.durationSeconds, 5.0);
  });

  test('transcribe throws on server error', () async {
    final dio = _errorDio(500, 'Internal Server Error');

    final api = TranscribeApi(dio);

    expect(
      () => api.transcribe(tempFile),
      throwsA(isA<DioException>()),
    );
  });

  test('TranscribeResult stores all fields', () {
    const result = TranscribeResult(
      transcript: 'Hello world',
      durationSeconds: 3.5,
      language: 'fr',
    );

    expect(result.transcript, 'Hello world');
    expect(result.durationSeconds, 3.5);
    expect(result.language, 'fr');
  });
}
