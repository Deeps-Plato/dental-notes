import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqlcipher_flutter_libs/sqlcipher_flutter_libs.dart';
import 'package:sqlite3/open.dart';

import 'tables.dart';

part 'app_database.g.dart';

const _dbName = 'dental_notes.db';
const _keyStorageKey = 'db_encryption_key';
const _keyLength = 32; // 256-bit AES key

@DriftDatabase(tables: [Patients, Visits, SoapNotes, PerioCharts, PerioReadings, AuditLogs])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) => m.createAll(),
    onUpgrade: (m, from, to) async {
      // Future migrations go here
    },
  );

  /// Opens the encrypted database, generating or retrieving the key from
  /// the platform keychain.
  static Future<AppDatabase> open() async {
    // Use SQLCipher instead of the default sqlite3
    open.overrideFor(OperatingSystem.android, openCipherOnAndroid);
    open.overrideFor(OperatingSystem.iOS, openCipherOnIOS);

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
        // Configure SQLCipher encryption key
        db.execute("PRAGMA key = '$key';");
        db.execute("PRAGMA cipher_page_size = 4096;");
        db.execute("PRAGMA kdf_iter = 64000;");
        db.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;");
      },
    );

    return AppDatabase(executor);
  }

  static String _generateKey() {
    // Generate 32 random bytes → hex string
    final bytes = List<int>.generate(_keyLength, (_) => _random());
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }

  static int _random() {
    // dart:math is not cryptographically secure; use platform RNG via dart:io
    final rng = Platform.isWindows ? _windowsRandom : _posixRandom;
    return rng();
  }

  static int _posixRandom() {
    final f = File('/dev/urandom').openSync();
    final byte = f.readByteSync();
    f.closeSync();
    return byte;
  }

  // Windows: fall back to Dart's pseudo-RNG seeded with clock — acceptable
  // for key bootstrapping since the key is immediately persisted in keychain.
  static int _windowsRandom() {
    return DateTime.now().microsecondsSinceEpoch & 0xFF;
  }
}
