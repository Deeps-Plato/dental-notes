import 'dart:convert';

import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/models/soap_note.dart' as models;
import 'package:dental_notes/data/repositories/soap_note_repository.dart';
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

models.SoapNote _sampleNote() => models.SoapNote(
  id: 0,
  visitId: 1,
  subjective: 'Patient reports pain in lower right.',
  objectiveClinical: 'Caries on #30 distal.',
  objectiveRadiographic: 'Periapical lucency #30.',
  objectiveVitals: null,
  assessment: 'Irreversible pulpitis #30.',
  planToday: ['Root canal #30'],
  planNextVisit: ['Crown prep #30'],
  planInstructions: ['Avoid chewing on right side'],
  cdtCodes: ['D3330'],
  medicationChanges: [
    const models.MedicationChange(
      drugName: 'ibuprofen',
      dose: '600mg',
      frequency: 'TID×3 days',
      changeType: 'prescribed',
      prescribingNote: 'for pain',
    ),
  ],
  createdAt: DateTime.now(),
  updatedAt: DateTime.now(),
);

void main() {
  late AppDatabase db;
  late SoapNoteRepository repo;

  setUp(() async {
    db = _openTestDb();
    repo = SoapNoteRepository(db);

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

  test('getForVisit returns null when no note exists', () async {
    final result = await repo.getForVisit(1);
    expect(result, isNull);
  });

  test('save creates note and returns ID', () async {
    final id = await repo.save(visitId: 1, note: _sampleNote());
    expect(id, greaterThan(0));
  });

  test('save then getForVisit round-trips correctly', () async {
    await repo.save(visitId: 1, note: _sampleNote());

    final row = await repo.getForVisit(1);
    expect(row, isNotNull);
    expect(row!.visitId, 1);
    expect(row.subjective, 'Patient reports pain in lower right.');
    expect(row.objectiveClinical, 'Caries on #30 distal.');
    expect(row.objectiveRadiographic, 'Periapical lucency #30.');
    expect(row.assessment, 'Irreversible pulpitis #30.');
  });

  test('save persists plan fields as JSON arrays', () async {
    await repo.save(visitId: 1, note: _sampleNote());

    final row = await repo.getForVisit(1);
    final planToday = jsonDecode(row!.planToday) as List;
    expect(planToday, ['Root canal #30']);

    final cdtCodes = jsonDecode(row.cdtCodes) as List;
    expect(cdtCodes, ['D3330']);
  });

  test('save persists medication changes as JSON', () async {
    await repo.save(visitId: 1, note: _sampleNote());

    final row = await repo.getForVisit(1);
    final meds = jsonDecode(row!.medicationChanges) as List;
    expect(meds.length, 1);
    expect(meds[0]['drugName'], 'ibuprofen');
    expect(meds[0]['dose'], '600mg');
  });

  test('save replaces existing note for same visit', () async {
    await repo.save(visitId: 1, note: _sampleNote());

    final updatedNote = _sampleNote().copyWith(
      subjective: 'Updated subjective',
      assessment: 'Updated assessment',
    );
    final newId = await repo.save(visitId: 1, note: updatedNote);

    final row = await repo.getForVisit(1);
    expect(row!.id, newId);
    expect(row.subjective, 'Updated subjective');
    expect(row.assessment, 'Updated assessment');

    // Only one note should exist for this visit.
    final allNotes = await db.select(db.soapNotes).get();
    expect(allNotes.length, 1);
  });

  test('updateFields modifies specific fields', () async {
    final id = await repo.save(visitId: 1, note: _sampleNote());

    await repo.updateFields(
      id,
      const SoapNotesCompanion(
        subjective: Value('Revised subjective'),
      ),
    );

    final row = await repo.getForVisit(1);
    expect(row!.subjective, 'Revised subjective');
    // Other fields unchanged
    expect(row.assessment, 'Irreversible pulpitis #30.');
  });

  test('watchForVisit emits note', () async {
    await repo.save(visitId: 1, note: _sampleNote());

    final note = await repo.watchForVisit(1).first;
    expect(note, isNotNull);
    expect(note!.subjective, 'Patient reports pain in lower right.');
  });

  test('save writes create audit log', () async {
    await repo.save(visitId: 1, note: _sampleNote());

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 1);
    expect(logs.first.action, 'create');
    expect(logs.first.entityType, 'soap_note');
  });

  test('updateFields writes update audit log', () async {
    final id = await repo.save(visitId: 1, note: _sampleNote());
    await repo.updateFields(
      id,
      const SoapNotesCompanion(subjective: Value('x')),
    );

    final logs = await db.select(db.auditLogs).get();
    expect(logs.length, 2);
    expect(logs[1].action, 'update');
    expect(logs[1].entityType, 'soap_note');
  });
}
