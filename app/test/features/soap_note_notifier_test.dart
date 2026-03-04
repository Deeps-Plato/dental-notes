import 'dart:convert';

import 'package:dental_notes/data/database/app_database.dart';
import 'package:dental_notes/data/models/soap_note.dart' as models;
import 'package:dental_notes/data/repositories/soap_note_repository.dart';
import 'package:dental_notes/features/soap_note/soap_note_notifier.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

AppDatabase _openTestDb() => AppDatabase(NativeDatabase.memory());

models.SoapNote _sampleNote() => models.SoapNote(
      id: 0,
      visitId: 1,
      subjective: 'Original subjective',
      objectiveClinical: 'Original clinical',
      objectiveRadiographic: 'Original radiographic',
      objectiveVitals: null,
      assessment: 'Original assessment',
      planToday: ['Step 1'],
      planNextVisit: ['Follow-up'],
      planInstructions: ['Brush twice daily'],
      cdtCodes: ['D0120'],
      medicationChanges: [],
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );

void main() {
  late AppDatabase db;
  late SoapNoteRepository repo;
  late SoapNoteActions actions;
  late int noteId;

  setUp(() async {
    db = _openTestDb();
    repo = SoapNoteRepository(db);
    actions = SoapNoteActions(repo);

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

    // Create the SOAP note we'll be editing.
    noteId = await repo.save(visitId: 1, note: _sampleNote());
  });

  tearDown(() => db.close());

  test('updateSubjective updates only subjective field', () async {
    await actions.updateSubjective(noteId, 'Revised subjective');

    final row = await repo.getForVisit(1);
    expect(row!.subjective, 'Revised subjective');
    expect(row.assessment, 'Original assessment'); // unchanged
  });

  test('updateObjectiveClinical updates clinical findings', () async {
    await actions.updateObjectiveClinical(noteId, 'New clinical');

    final row = await repo.getForVisit(1);
    expect(row!.objectiveClinical, 'New clinical');
  });

  test('updateObjectiveRadiographic updates radiographic findings', () async {
    await actions.updateObjectiveRadiographic(noteId, 'New radiographic');

    final row = await repo.getForVisit(1);
    expect(row!.objectiveRadiographic, 'New radiographic');
  });

  test('updateAssessment updates assessment', () async {
    await actions.updateAssessment(noteId, 'New assessment');

    final row = await repo.getForVisit(1);
    expect(row!.assessment, 'New assessment');
  });

  test('updatePlanToday persists JSON array', () async {
    await actions.updatePlanToday(noteId, ['Step A', 'Step B']);

    final row = await repo.getForVisit(1);
    final decoded = jsonDecode(row!.planToday) as List;
    expect(decoded, ['Step A', 'Step B']);
  });

  test('updatePlanNextVisit persists JSON array', () async {
    await actions.updatePlanNextVisit(noteId, ['Crown prep']);

    final row = await repo.getForVisit(1);
    final decoded = jsonDecode(row!.planNextVisit) as List;
    expect(decoded, ['Crown prep']);
  });

  test('updatePlanInstructions persists JSON array', () async {
    await actions.updatePlanInstructions(
      noteId,
      ['No hot food', 'Take meds as directed'],
    );

    final row = await repo.getForVisit(1);
    final decoded = jsonDecode(row!.planInstructions) as List;
    expect(decoded, ['No hot food', 'Take meds as directed']);
  });

  test('updateCdtCodes persists JSON array', () async {
    await actions.updateCdtCodes(noteId, ['D2391', 'D2392']);

    final row = await repo.getForVisit(1);
    final decoded = jsonDecode(row!.cdtCodes) as List;
    expect(decoded, ['D2391', 'D2392']);
  });

  test('each update writes audit log', () async {
    // The save in setUp already created 1 audit log entry.
    await actions.updateSubjective(noteId, 'v2');
    await actions.updateAssessment(noteId, 'v2');

    final logs = await db.select(db.auditLogs).get();
    // 1 (create from setUp) + 2 (updates)
    expect(logs.length, 3);
    expect(logs[1].action, 'update');
    expect(logs[2].action, 'update');
  });
}
