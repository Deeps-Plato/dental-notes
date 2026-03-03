import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/soap_note.dart' as models;
import '../soap_note/soap_note_notifier.dart';

class MedicationsScreen extends ConsumerWidget {
  const MedicationsScreen({super.key, required this.visitId});

  final String visitId;

  int get _visitId => int.parse(visitId);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final noteAsync = ref.watch(soapNoteForVisitProvider(_visitId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Medications'),
      ),
      body: noteAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
        data: (soapNote) {
          if (soapNote == null) {
            return const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                spacing: 12,
                children: [
                  Icon(Icons.medication_outlined, size: 64, color: Colors.grey),
                  Text(
                    'No SOAP note for this visit yet.\n'
                    'Generate a note to see medication changes.',
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            );
          }

          final meds = _decodeMedications(soapNote.medicationChanges);
          if (meds.isEmpty) {
            return const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                spacing: 12,
                children: [
                  Icon(Icons.check_circle_outline, size: 64, color: Colors.grey),
                  Text(
                    'No medication changes\nrecorded for this visit.',
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: meds.length,
            separatorBuilder: (_, __) => const Divider(),
            itemBuilder: (context, index) => _MedicationTile(med: meds[index]),
          );
        },
      ),
    );
  }

  List<models.MedicationChange> _decodeMedications(String? raw) {
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      return list.map(models.MedicationChange.fromJson).toList();
    } catch (_) {
      return [];
    }
  }
}

class _MedicationTile extends StatelessWidget {
  const _MedicationTile({required this.med});

  final models.MedicationChange med;

  @override
  Widget build(BuildContext context) {
    final icon = switch (med.changeType) {
      'prescribed' => Icons.add_circle,
      'discontinued' => Icons.remove_circle,
      'modified' => Icons.edit,
      'refilled' => Icons.refresh,
      _ => Icons.medication,
    };

    final color = switch (med.changeType) {
      'prescribed' => Colors.green,
      'discontinued' => Colors.red,
      'modified' => Colors.orange,
      _ => Colors.blue,
    };

    return ListTile(
      leading: Icon(icon, color: color),
      title: Text(
        med.drugName,
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${med.dose} — ${med.frequency}'),
          Chip(
            label: Text(
              med.changeType.toUpperCase(),
              style: TextStyle(fontSize: 10, color: color),
            ),
            padding: EdgeInsets.zero,
            visualDensity: VisualDensity.compact,
            side: BorderSide(color: color),
            backgroundColor: color.withValues(alpha: 0.1),
          ),
          if (med.prescribingNote != null && med.prescribingNote!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                med.prescribingNote!,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ),
      isThreeLine: true,
    );
  }
}
