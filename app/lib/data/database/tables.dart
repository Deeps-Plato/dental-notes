import 'package:drift/drift.dart';

// ── Patients ──────────────────────────────────────────────────────────────────

class Patients extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get firstName => text().withLength(min: 1, max: 100)();
  TextColumn get lastName => text().withLength(min: 1, max: 100)();
  DateTimeColumn get dateOfBirth => dateTime()();
  TextColumn get phone => text().nullable()();
  TextColumn get email => text().nullable()();
  TextColumn get allergies => text().nullable()();
  TextColumn get medicalHistory => text().nullable()();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

// ── Visits ────────────────────────────────────────────────────────────────────

class Visits extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get patientId => integer().references(Patients, #id)();
  DateTimeColumn get visitDate => dateTime()();
  TextColumn get chiefComplaint => text().nullable()();
  TextColumn get provider => text().nullable()();
  TextColumn get rawTranscript => text().nullable()();
  BoolColumn get isComplete => boolean().withDefault(const Constant(false))();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

// ── SOAP Notes ────────────────────────────────────────────────────────────────

class SoapNotes extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get visitId => integer().references(Visits, #id)();
  TextColumn get subjective => text().withDefault(const Constant(''))();
  TextColumn get objectiveClinical => text().withDefault(const Constant(''))();
  TextColumn get objectiveRadiographic => text().nullable()();
  TextColumn get objectiveVitals => text().nullable()();
  TextColumn get assessment => text().withDefault(const Constant(''))();
  // plan stored as JSON arrays
  TextColumn get planToday => text().withDefault(const Constant('[]'))();
  TextColumn get planNextVisit => text().withDefault(const Constant('[]'))();
  TextColumn get planInstructions => text().withDefault(const Constant('[]'))();
  TextColumn get cdtCodes => text().withDefault(const Constant('[]'))();
  // medication_changes as JSON array
  TextColumn get medicationChanges => text().withDefault(const Constant('[]'))();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

// ── Perio Charts ──────────────────────────────────────────────────────────────

class PerioCharts extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get visitId => integer().references(Visits, #id)();
  // Computed AAP classification
  TextColumn get aapStage => text().nullable()();
  TextColumn get aapGrade => text().nullable()();
  RealColumn get bopPercent => real().nullable()();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

// ── Perio Readings — one row per tooth/surface ────────────────────────────────

class PerioReadings extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get chartId => integer().references(PerioCharts, #id)();
  IntColumn get toothNumber => integer()();  // 1–32
  TextColumn get surface => text()();        // 'buccal' | 'lingual'
  IntColumn get depthMb => integer()();
  IntColumn get depthB => integer()();
  IntColumn get depthDb => integer()();
  BoolColumn get bop => boolean().withDefault(const Constant(false))();
  IntColumn get recession => integer().withDefault(const Constant(0))();
}

// ── Odontograms — one per visit, tooth data stored as JSON ────────────────

class Odontograms extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get visitId => integer().references(Visits, #id)();
  // JSON-encoded Map<int, ToothRecord> (see data/models/odontogram.dart)
  TextColumn get teethJson => text().withDefault(const Constant('{}'))();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

// ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLogs extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get action => text()();           // e.g. 'create', 'update', 'delete'
  TextColumn get entityType => text()();       // e.g. 'patient', 'visit', 'soap_note'
  IntColumn get entityId => integer()();
  DateTimeColumn get timestamp => dateTime().withDefault(currentDateAndTime)();
}
