import 'package:drift/drift.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../domain/perio_logic.dart';
import '../../shared/providers/database_provider.dart';
import '../database/app_database.dart';
import '../models/perio_chart.dart' as models;

part 'perio_repository.g.dart';

@riverpod
PerioRepository perioRepository(PerioRepositoryRef ref) {
  final db = ref.watch(databaseProvider);
  return PerioRepository(db);
}

class PerioRepository {
  PerioRepository(this._db);
  final AppDatabase _db;

  /// Watch the perio chart for a visit (one chart per visit).
  Stream<PerioChart?> watchChartForVisit(int visitId) {
    final query = _db.select(_db.perioCharts)
      ..where((t) => t.visitId.equals(visitId));
    return query.watchSingleOrNull();
  }

  /// Get all readings for a chart.
  Future<List<PerioReading>> getReadingsForChart(int chartId) {
    final query = _db.select(_db.perioReadings)
      ..where((t) => t.chartId.equals(chartId))
      ..orderBy([
        (t) => OrderingTerm(expression: t.toothNumber),
        (t) => OrderingTerm(expression: t.surface),
      ]);
    return query.get();
  }

  /// Watch all readings for a chart.
  Stream<List<PerioReading>> watchReadingsForChart(int chartId) {
    final query = _db.select(_db.perioReadings)
      ..where((t) => t.chartId.equals(chartId))
      ..orderBy([
        (t) => OrderingTerm(expression: t.toothNumber),
        (t) => OrderingTerm(expression: t.surface),
      ]);
    return query.watch();
  }

  /// Create or get the perio chart for a visit. Returns chart ID.
  Future<int> ensureChart(int visitId) async {
    final existing = await (_db.select(_db.perioCharts)
          ..where((t) => t.visitId.equals(visitId)))
        .getSingleOrNull();

    if (existing != null) return existing.id;

    final id = await _db.into(_db.perioCharts).insert(
      PerioChartsCompanion.insert(visitId: visitId),
    );
    await _audit('create', 'perio_chart', id);
    return id;
  }

  /// Upsert a single perio reading (by chart + tooth + surface).
  Future<void> saveReading({
    required int chartId,
    required models.PerioReading reading,
  }) async {
    // Delete existing reading for this tooth/surface
    await (_db.delete(_db.perioReadings)
          ..where((t) =>
              t.chartId.equals(chartId) &
              t.toothNumber.equals(reading.toothNumber) &
              t.surface.equals(reading.surface),))
        .go();

    final id = await _db.into(_db.perioReadings).insert(
      PerioReadingsCompanion.insert(
        chartId: chartId,
        toothNumber: reading.toothNumber,
        surface: reading.surface,
        depthMb: reading.depthMb,
        depthB: reading.depthB,
        depthDb: reading.depthDb,
        bop: Value(reading.bop),
        recession: Value(reading.recession),
      ),
    );
    await _audit('update', 'perio_reading', id);
  }

  /// Batch-save multiple readings (from voice parse).
  Future<void> saveReadings({
    required int chartId,
    required List<models.PerioReading> readings,
  }) async {
    await _db.transaction(() async {
      for (final r in readings) {
        await saveReading(chartId: chartId, reading: r);
      }
    });
    await _recalculateClassification(chartId);
  }

  /// Recalculate AAP Stage/Grade from current readings and update chart.
  Future<void> _recalculateClassification(int chartId) async {
    final readings = await getReadingsForChart(chartId);
    final modelReadings = readings.map(_toModelReading).toList();

    final stage = PerioLogic.calculateStage(modelReadings);
    final grade = PerioLogic.calculateGrade(modelReadings);
    final bopPct = PerioLogic.calculateBopPercent(modelReadings);

    await (_db.update(_db.perioCharts)
          ..where((t) => t.id.equals(chartId)))
        .write(PerioChartsCompanion(
      aapStage: Value(stage),
      aapGrade: Value(grade),
      bopPercent: Value(bopPct),
      updatedAt: Value(DateTime.now()),
    ),);
  }

  models.PerioReading _toModelReading(PerioReading row) => models.PerioReading(
    id: row.id,
    chartId: row.chartId,
    toothNumber: row.toothNumber,
    surface: row.surface,
    depthMb: row.depthMb,
    depthB: row.depthB,
    depthDb: row.depthDb,
    bop: row.bop,
    recession: row.recession,
  );

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
