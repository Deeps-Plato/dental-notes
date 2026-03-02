import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/soap_note.dart';

class SoapNoteScreen extends ConsumerStatefulWidget {
  const SoapNoteScreen({super.key, required this.visitId});

  final String visitId;

  @override
  ConsumerState<SoapNoteScreen> createState() => _SoapNoteScreenState();
}

class _SoapNoteScreenState extends ConsumerState<SoapNoteScreen> {
  final _subjectiveCtrl = TextEditingController();
  final _clinicalCtrl = TextEditingController();
  final _radiographicCtrl = TextEditingController();
  final _assessmentCtrl = TextEditingController();

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
    return Scaffold(
      appBar: AppBar(
        title: const Text('SOAP Note'),
        actions: [
          FilledButton.icon(
            onPressed: _save,
            icon: const Icon(Icons.save),
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
          // TODO: Plan section with chips for CDT codes
          const _PlanSection(),
          const SizedBox(height: 12),
          // TODO: Medication changes section
          const _MedicationsSection(),
        ],
      ),
    );
  }

  void _save() {
    // TODO: persist via SoapNote repository
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Note saved')),
    );
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
  const _PlanSection();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Text('P — Plan', style: Theme.of(context).textTheme.labelLarge),
        // TODO: editable lists for today/next-visit/instructions/CDT codes
        const Card(
          child: Padding(
            padding: EdgeInsets.all(12),
            child: Text('Today's procedures, next visit, instructions, CDT codes…'),
          ),
        ),
      ],
    );
  }
}

class _MedicationsSection extends StatelessWidget {
  const _MedicationsSection();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Text('Medication Changes', style: Theme.of(context).textTheme.labelLarge),
        // TODO: list of MedicationChange tiles
        const Card(
          child: Padding(
            padding: EdgeInsets.all(12),
            child: Text('No medication changes recorded.'),
          ),
        ),
      ],
    );
  }
}
