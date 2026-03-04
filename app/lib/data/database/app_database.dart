import 'dart:io';
import 'dart:math' as math;

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqlcipher_flutter_libs/sqlcipher_flutter_libs.dart';
import 'package:sqlite3/open.dart' as sqlite3_open;

import 'tables.dart';

part 'app_database.g.dart';

const _dbName = 'dental_notes.db';
const _keyStorageKey = 'db_encryption_key';
const _keyLength = 32; // 256-bit AES key

@DriftDatabase(tables: [
  Patients, Visits, SoapNotes, PerioCharts, PerioReadings, Odontograms, AuditLogs,
],)
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  @override
  int get schemaVersion => 2;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) => m.createAll(),
    onUpgrade: (m, from, to) async {
      if (from < 2) {
        await m.createTable(odontograms);
      }
    },
  );

  /// Opens the encrypted database, generating or retrieving the key from
  /// the platform keychain.
  static Future<AppDatabase> openEncrypted() async {
    // Use SQLCipher instead of the default sqlite3
    if (Platform.isAndroid) {
      sqlite3_open.open.overrideFor(
        sqlite3_open.OperatingSystem.android,
        openCipherOnAndroid,
      );
    }

    const storage = FlutterSecureStorage();
    var key = await storage.read(key: _keyStorageKey);
    if (key == null) {
      key = _generateKey();
      await storage.write(key: _keyStorageKey, value: key);
    }

    final dir = await getApplicationDocumentsDirectory();
    final dbFile = File(p.join(dir.path, _dbName));

    final executor = NativeDatabase(
      dbFile,
      setup: (db) {
        db.execute("PRAGMA key = '$key';");
      },
    );

    return AppDatabase(executor);
  }

  static String _generateKey() {
    final rng = math.Random.secure();
    final bytes = List<int>.generate(_keyLength, (_) => rng.nextInt(256));
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }
}
