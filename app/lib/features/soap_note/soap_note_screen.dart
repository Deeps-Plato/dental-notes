import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/database/app_database.dart';
import 'soap_note_notifier.dart';

class SoapNoteScreen extends ConsumerWidget {
  const SoapNoteScreen({super.key, required this.visitId});

  final String visitId;

  int get _visitId => int.parse(visitId);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final noteAsync = ref.watch(soapNoteForVisitProvider(_visitId));

    return noteAsync.when(
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Scaffold(
        appBar: AppBar(title: const Text('SOAP Note')),
        body: Center(child: Text('Error: $e')),
      ),
      data: (noteRow) {
        if (noteRow == null) {
          return Scaffold(
            appBar: AppBar(title: const Text('SOAP Note')),
            body: const Center(
              child: Text(
                'No note yet.\nGo to Recording and tap "Generate Note".',
                textAlign: TextAlign.center,
              ),
            ),
          );
        }
        return _NoteEditor(note: noteRow);
      },
    );
  }
}

class _NoteEditor extends ConsumerStatefulWidget {
  const _NoteEditor({required this.note});
  final SoapNote note;

  @override
  ConsumerState<_NoteEditor> createState() => _NoteEditorState();
}

class _NoteEditorState extends ConsumerState<_NoteEditor> {
  late final TextEditingController _subjectiveCtrl;
  late final TextEditingController _clinicalCtrl;
  late final TextEditingController _radiographicCtrl;
  late final TextEditingController _assessmentCtrl;

  @override
  void initState() {
    super.initState();
    _subjectiveCtrl = TextEditingController(text: widget.note.subjective);
    _clinicalCtrl =
        TextEditingController(text: widget.note.objectiveClinical);
    _radiographicCtrl =
        TextEditingController(text: widget.note.objectiveRadiographic ?? '');
    _assessmentCtrl = TextEditingController(text: widget.note.assessment);
  }

  @override
  void dispose() {
    _subjectiveCtrl.dispose();
    _clinicalCtrl.dispose();
    _radiographicCtrl.dispose();
    _assessmentCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final actions = ref.read(soapNoteActionsProvider);
    final noteId = widget.note.id;

    // Decode JSON arrays for plan fields
    final planToday = _decodeList(widget.note.planToday);
    final planNextVisit = _decodeList(widget.note.planNextVisit);
    final planInstructions = _decodeList(widget.note.planInstructions);
    final cdtCodes = _decodeList(widget.note.cdtCodes);
    final meds = _decodeList(widget.note.medicationChanges);

    return Scaffold(
      appBar: AppBar(
        title: const Text('SOAP Note'),
        actions: [
          FilledButton.icon(
            onPressed: () => _saveAll(actions, noteId),
            icon: const Icon(Icons.save, size: 18),
            label: const Text('Save'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SoapSection(
            label: 'S — Subjective',
            controller: _subjectiveCtrl,
            hint: 'Chief complaint and patient-reported symptoms…',
            maxLines: 4,
          ),
          const SizedBox(height: 12),
          _SoapSection(
            label: 'O — Objective (Clinical)',
            controller: _clinicalCtrl,
            hint: 'Clinical examination findings…',
            maxLines: 4,
          ),
          const SizedBox(height: 12),
          _SoapSection(
            label: 'O — Objective (Radiographic)',
            controller: _radiographicCtrl,
            hint: 'Radiographic findings, or leave blank…',
            maxLines: 3,
          ),
          const SizedBox(height: 12),
          _SoapSection(
            label: 'A — Assessment',
            controller: _assessmentCtrl,
            hint: 'Diagnoses and clinical impressions…',
            maxLines: 3,
          ),
          const SizedBox(height: 12),
          _PlanSection(
            todayItems: planToday,
            nextVisitItems: planNextVisit,
            instructionItems: planInstructions,
            cdtCodes: cdtCodes,
          ),
          const SizedBox(height: 12),
          _MedicationsSection(medications: meds),
        ],
      ),
    );
  }

  Future<void> _saveAll(SoapNoteActions actions, int noteId) async {
    try {
      await actions.updateSubjective(noteId, _subjectiveCtrl.text);
      await actions.updateObjectiveClinical(noteId, _clinicalCtrl.text);
      await actions.updateObjectiveRadiographic(
        noteId,
        _radiographicCtrl.text.isEmpty ? null : _radiographicCtrl.text,
      );
      await actions.updateAssessment(noteId, _assessmentCtrl.text);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Note saved')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Save failed: $e')),
        );
      }
    }
  }

  List<String> _decodeList(dynamic value) {
    if (value is String) {
      try {
        return (jsonDecode(value) as List).cast<String>();
      } catch (_) {
        return [];
      }
    }
    return [];
  }
}

class _SoapSection extends StatelessWidget {
  const _SoapSection({
    required this.label,
    required this.controller,
    required this.hint,
    this.maxLines = 3,
  });

  final String label;
  final TextEditingController controller;
  final String hint;
  final int maxLines;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 4,
      children: [
        Text(label, style: Theme.of(context).textTheme.labelLarge),
        TextFormField(
          controller: controller,
          decoration: InputDecoration(hintText: hint),
          maxLines: maxLines,
        ),
      ],
    );
  }
}

class _PlanSection extends StatelessWidget {
  const _PlanSection({
    required this.todayItems,
    required this.nextVisitItems,
    required this.instructionItems,
    required this.cdtCodes,
  });

  final List<String> todayItems;
  final List<String> nextVisitItems;
  final List<String> instructionItems;
  final List<String> cdtCodes;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Text('P — Plan', style: Theme.of(context).textTheme.labelLarge),
        _BulletList(title: "Today's Procedures", items: todayItems),
        _BulletList(title: 'Next Visit', items: nextVisitItems),
        _BulletList(title: 'Patient Instructions', items: instructionItems),
        if (cdtCodes.isNotEmpty) ...[
          Text('CDT Codes', style: Theme.of(context).textTheme.labelMedium),
          Wrap(
            spacing: 6,
            children: cdtCodes
                .map((c) => Chip(
                      label: Text(c, style: const TextStyle(fontSize: 12)),
                    ),)
                .toList(),
          ),
        ],
      ],
    );
  }
}

class _BulletList extends StatelessWidget {
  const _BulletList({required this.title, required this.items});
  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.labelMedium),
            const SizedBox(height: 4),
            ...items.map(
              (item) => Padding(
                padding: const EdgeInsets.only(left: 8, bottom: 2),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('  •  '),
                    Expanded(child: Text(item)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MedicationsSection extends StatelessWidget {
  const _MedicationsSection({required this.medications});
  final List<String> medications;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Text('Medication Changes',
            style: Theme.of(context).textTheme.labelLarge,),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: medications.isEmpty
                ? const Text('No medication changes recorded.')
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: medications.map((m) => Text(m)).toList(),
                  ),
          ),
        ),
      ],
    );
  }
}
