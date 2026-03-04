import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/models/perio_chart.dart' as models;
import 'package:dental_notes/data/repositories/perio_repository.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

void main() {
  late AppDatabase db;
  late PerioRepository repo;

  setUp(() async {
    db = _openTestDb();
    repo = PerioRepository(db);

    // Insert patient + visit for FK constraints.
    await db.into(db.patients).insert(PatientsCompanion.insert(
      firstName: 'Test',
      lastName: 'Patient',
      dateOfBirth: DateTime(1990, 1, 1),
    ),);
    await db.into(db.visits).insert(VisitsCompanion.insert(
      patientId: 1,
      visitDate: DateTime(2024, 6, 15),
    ),);
  });

  tearDown(() => db.close());

  group('ensureChart', () {
    test('creates new chart and returns ID', () async {
      final chartId = await repo.ensureChart(1);
      expect(chartId, greaterThan(0));
    });

    test('returns existing chart ID on second call', () async {
      final id1 = await repo.ensureChart(1);
      final id2 = await repo.ensureChart(1);
      expect(id1, id2);
    });

    test('creates separate charts for different visits', () async {
      // Add second visit.
      await db.into(db.visits).insert(VisitsCompanion.insert(
        patientId: 1,
        visitDate: DateTime(2024, 7, 1),
      ),);

      final id1 = await repo.ensureChart(1);
      final id2 = await repo.ensureChart(2);
      expect(id1, isNot(id2));
    });

    test('writes create audit log', () async {
      await repo.ensureChart(1);

      final logs = await db.select(db.auditLogs).get();
      expect(logs.length, 1);
      expect(logs.first.action, 'create');
      expect(logs.first.entityType, 'perio_chart');
    });
  });

  group('saveReading', () {
    test('inserts reading and retrieves it', () async {
      final chartId = await repo.ensureChart(1);

      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'buccal',
          depthMb: 3,
          depthB: 2,
          depthDb: 4,
          bop: true,
          recession: 1,
        ),
      );

      final readings = await repo.getReadingsForChart(chartId);
      expect(readings.length, 1);
      expect(readings.first.toothNumber, 14);
      expect(readings.first.surface, 'buccal');
      expect(readings.first.depthMb, 3);
      expect(readings.first.depthB, 2);
      expect(readings.first.depthDb, 4);
      expect(readings.first.bop, true);
      expect(readings.first.recession, 1);
    });

    test('upserts reading for same tooth/surface', () async {
      final chartId = await repo.ensureChart(1);

      // First reading
      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'buccal',
          depthMb: 3,
          depthB: 2,
          depthDb: 4,
          bop: false,
          recession: 0,
        ),
      );

      // Updated reading for same tooth/surface
      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'buccal',
          depthMb: 5,
          depthB: 4,
          depthDb: 6,
          bop: true,
          recession: 2,
        ),
      );

      final readings = await repo.getReadingsForChart(chartId);
      expect(readings.length, 1); // still one reading
      expect(readings.first.depthMb, 5);
      expect(readings.first.bop, true);
      expect(readings.first.recession, 2);
    });

    test('different surfaces create separate readings', () async {
      final chartId = await repo.ensureChart(1);

      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'buccal',
          depthMb: 3,
          depthB: 2,
          depthDb: 4,
          bop: false,
          recession: 0,
        ),
      );
      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'lingual',
          depthMb: 2,
          depthB: 2,
          depthDb: 3,
          bop: false,
          recession: 0,
        ),
      );

      final readings = await repo.getReadingsForChart(chartId);
      expect(readings.length, 2);
    });
  });

  group('saveReadings (batch)', () {
    test('saves multiple readings in a transaction', () async {
      final chartId = await repo.ensureChart(1);

      await repo.saveReadings(
        chartId: chartId,
        readings: const [
          models.PerioReading(
            id: 0,
            chartId: 0,
            toothNumber: 14,
            surface: 'buccal',
            depthMb: 3,
            depthB: 2,
            depthDb: 4,
            bop: false,
            recession: 0,
          ),
          models.PerioReading(
            id: 0,
            chartId: 0,
            toothNumber: 19,
            surface: 'buccal',
            depthMb: 5,
            depthB: 4,
            depthDb: 6,
            bop: true,
            recession: 1,
          ),
        ],
      );

      final readings = await repo.getReadingsForChart(chartId);
      expect(readings.length, 2);
    });

    test('recalculates AAP classification after batch save', () async {
      final chartId = await repo.ensureChart(1);

      // Save readings with max depth 6 → Stage III, some BOP
      await repo.saveReadings(
        chartId: chartId,
        readings: const [
          models.PerioReading(
            id: 0,
            chartId: 0,
            toothNumber: 14,
            surface: 'buccal',
            depthMb: 3,
            depthB: 2,
            depthDb: 6,
            bop: true,
            recession: 0,
          ),
          models.PerioReading(
            id: 0,
            chartId: 0,
            toothNumber: 19,
            surface: 'buccal',
            depthMb: 2,
            depthB: 2,
            depthDb: 3,
            bop: false,
            recession: 0,
          ),
        ],
      );

      final chart = await repo.watchChartForVisit(1).first;
      expect(chart, isNotNull);
      expect(chart!.aapStage, 'III'); // max depth ≥ 6
      expect(chart.aapGrade, isNotNull);
      expect(chart.bopPercent, isNotNull);
    });
  });

  group('getReadingsForChart ordering', () {
    test('returns readings ordered by tooth then surface', () async {
      final chartId = await repo.ensureChart(1);

      // Insert in reverse order
      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 19,
          surface: 'lingual',
          depthMb: 2,
          depthB: 2,
          depthDb: 2,
          bop: false,
          recession: 0,
        ),
      );
      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'buccal',
          depthMb: 3,
          depthB: 3,
          depthDb: 3,
          bop: false,
          recession: 0,
        ),
      );

      final readings = await repo.getReadingsForChart(chartId);
      expect(readings[0].toothNumber, 14);
      expect(readings[1].toothNumber, 19);
    });
  });

  group('watchReadingsForChart', () {
    test('emits readings as a stream', () async {
      final chartId = await repo.ensureChart(1);

      await repo.saveReading(
        chartId: chartId,
        reading: const models.PerioReading(
          id: 0,
          chartId: 0,
          toothNumber: 14,
          surface: 'buccal',
          depthMb: 3,
          depthB: 2,
          depthDb: 4,
          bop: false,
          recession: 0,
        ),
      );

      final readings = await repo.watchReadingsForChart(chartId).first;
      expect(readings.length, 1);
      expect(readings.first.toothNumber, 14);
    });
  });
}
