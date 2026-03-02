import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/database/app_database.dart';

part 'database_provider.g.dart';

/// Synchronous provider — the database is opened in main() and injected
/// via ProviderScope override before any widget builds.
@riverpod
AppDatabase database(DatabaseRef ref) => throw UnimplementedError(
  'databaseProvider must be overridden in ProviderScope',
);
