import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'api_client.g.dart';

const _baseUrlKey = 'backend_base_url';
const _apiKeyKey = 'backend_api_key';
const _defaultBaseUrl = 'http://localhost:8765';

@riverpod
Future<ApiClient> apiClient(ApiClientRef ref) async {
  const storage = FlutterSecureStorage();
  final baseUrl = await storage.read(key: _baseUrlKey) ?? _defaultBaseUrl;
  final apiKey = await storage.read(key: _apiKeyKey) ?? '';
  return ApiClient(baseUrl: baseUrl, apiKey: apiKey);
}

class ApiClient {
  ApiClient({required String baseUrl, required String apiKey})
      : _dio = _buildDio(baseUrl, apiKey);

  final Dio _dio;

  static Dio _buildDio(String baseUrl, String apiKey) {
    final dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 60),
        sendTimeout: const Duration(seconds: 30),
        headers: {
          'X-API-Key': apiKey,
        },
      ),
    );

    // Reject non-HTTPS connections in production (ngrok/Tailscale provide TLS)
    // Allow HTTP only for localhost during development
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final isLocalhost = options.uri.host == 'localhost' ||
              options.uri.host == '127.0.0.1';
          if (!isLocalhost && options.uri.scheme != 'https') {
            handler.reject(
              DioException(
                requestOptions: options,
                message: 'Plain HTTP rejected — use HTTPS (ngrok or Tailscale)',
              ),
            );
            return;
          }
          handler.next(options);
        },
      ),
    );

    return dio;
  }

  Dio get dio => _dio;
}
