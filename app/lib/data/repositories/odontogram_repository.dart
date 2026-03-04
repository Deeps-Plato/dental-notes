import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../shared/providers/database_provider.dart';
import '../database/app_database.dart';
import '../models/odontogram.dart' as models;

part 'odontogram_repository.g.dart';

@riverpod
OdontogramRepository odontogramRepository(OdontogramRepositoryRef ref) {
  final db = ref.watch(databaseProvider);
  return OdontogramRepository(db);
}

class OdontogramRepository {
  OdontogramRepository(this._db);
  final AppDatabase _db;

  /// Watch the odontogram for a visit.
  Stream<models.Odontogram?> watchForVisit(int visitId) {
    final query = _db.select(_db.odontograms)
      ..where((t) => t.visitId.equals(visitId));
    return query.watchSingleOrNull().map((row) {
      if (row == null) return null;
      return _fromRow(row, visitId);
    });
  }

  /// Get the odontogram for a visit.
  Future<models.Odontogram?> getForVisit(int visitId) async {
    final row = await (_db.select(_db.odontograms)
          ..where((t) => t.visitId.equals(visitId)))
        .getSingleOrNull();
    if (row == null) return null;
    return _fromRow(row, visitId);
  }

  /// Save (create or update) the odontogram for a visit.
  Future<void> save(models.Odontogram odontogram) async {
    final json = _teethToJson(odontogram.teeth);

    final existing = await (_db.select(_db.odontograms)
          ..where((t) => t.visitId.equals(odontogram.visitId)))
        .getSingleOrNull();

    if (existing != null) {
      await (_db.update(_db.odontograms)
            ..where((t) => t.id.equals(existing.id)))
          .write(OdontogramsCompanion(
        teethJson: Value(json),
        updatedAt: Value(DateTime.now()),
      ),);
      await _audit('update', 'odontogram', existing.id);
    } else {
      final id = await _db.into(_db.odontograms).insert(
        OdontogramsCompanion.insert(
          visitId: odontogram.visitId,
          teethJson: Value(json),
        ),
      );
      await _audit('create', 'odontogram', id);
    }
  }

  models.Odontogram _fromRow(Odontogram row, int visitId) {
    final decoded = jsonDecode(row.teethJson) as Map<String, dynamic>;
    final teeth = <int, models.ToothRecord>{};
    for (final entry in decoded.entries) {
      final toothNum = int.parse(entry.key);
      teeth[toothNum] =
          models.ToothRecord.fromJson(entry.value as Map<String, dynamic>);
    }
    return models.Odontogram(visitId: visitId, teeth: teeth);
  }

  String _teethToJson(Map<int, models.ToothRecord> teeth) {
    final map = <String, dynamic>{};
    for (final entry in teeth.entries) {
      map[entry.key.toString()] = entry.value.toJson();
    }
    return jsonEncode(map);
  }

  Future<void> _audit(String action, String entityType, int entityId) async {
    await _db.into(_db.auditLogs).insert(
      AuditLogsCompanion.insert(
        action: action,
        entityType: entityType,
        entityId: entityId,
      ),
    );
  }
}
