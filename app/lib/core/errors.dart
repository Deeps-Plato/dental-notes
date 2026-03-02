/// Application error types for typed error handling.
library;

sealed class AppError {
  const AppError(this.message);
  final String message;
}

final class NetworkError extends AppError {
  const NetworkError(super.message, {this.statusCode});
  final int? statusCode;
}

final class AuthError extends AppError {
  const AuthError(super.message);
}

final class TranscriptionError extends AppError {
  const TranscriptionError(super.message);
}

final class NoteGenerationError extends AppError {
  const NoteGenerationError(super.message);
}

final class StorageError extends AppError {
  const StorageError(super.message);
}

final class PermissionError extends AppError {
  const PermissionError(super.message);
}
