import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/database/app_database.dart';
import '../../data/repositories/visit_repository.dart';
import '../visit/visit_notifier.dart';
import 'patients_notifier.dart';

class PatientDetailScreen extends ConsumerWidget {
  const PatientDetailScreen({super.key, required this.patientId});

  final String patientId;

  int get _id => int.parse(patientId);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final patientAsync = ref.watch(patientDetailProvider(_id));

    return patientAsync.when(
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Scaffold(
        appBar: AppBar(),
        body: Center(child: Text('Error: $e')),
      ),
      data: (patient) {
        if (patient == null) {
          return Scaffold(
            appBar: AppBar(),
            body: const Center(child: Text('Patient not found')),
          );
        }
        return _Body(patient: patient);
      },
    );
  }
}

class _Body extends ConsumerWidget {
  const _Body({required this.patient});
  final Patient patient;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${patient.lastName}, ${patient.firstName}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: () => _confirmDelete(context, ref),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _PatientInfoCard(patient: patient),
          const SizedBox(height: 16),
          _VisitHistory(patientId: patient.id),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _startNewVisit(context, ref),
        icon: const Icon(Icons.add_circle_outline),
        label: const Text('New Visit'),
      ),
    );
  }

  Future<void> _startNewVisit(BuildContext context, WidgetRef ref) async {
    final repo = ref.read(visitRepositoryProvider);
    final visitId = await repo.create(
      patientId: patient.id,
      visitDate: DateTime.now(),
    );
    if (context.mounted) {
      context.go('/patients/${patient.id}/visit/$visitId');
    }
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Patient?'),
        content: Text(
          'This will permanently delete ${patient.firstName} '
          '${patient.lastName} and all their visits.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      final actions = ref.read(patientActionsProvider);
      await actions.delete(patient.id);
      if (context.mounted) context.go('/patients');
    }
  }
}

class _PatientInfoCard extends StatelessWidget {
  const _PatientInfoCard({required this.patient});
  final Patient patient;

  @override
  Widget build(BuildContext context) {
    final dob = patient.dateOfBirth;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 8,
          children: [
            Text('Patient Info',
                style: Theme.of(context).textTheme.titleMedium,),
            _InfoRow('Name', '${patient.firstName} ${patient.lastName}'),
            _InfoRow(
              'DOB',
              '${dob.year}-${dob.month.toString().padLeft(2, '0')}'
              '-${dob.day.toString().padLeft(2, '0')}',
            ),
            if (patient.phone != null) _InfoRow('Phone', patient.phone!),
            if (patient.email != null) _InfoRow('Email', patient.email!),
            if (patient.allergies != null)
              _InfoRow('Allergies', patient.allergies!),
            if (patient.medicalHistory != null)
              _InfoRow('Medical History', patient.medicalHistory!),
          ],
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 120,
          child: Text(
            label,
            style: Theme.of(context)
                .textTheme
                .bodyMedium
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
        Expanded(child: Text(value)),
      ],
    );
  }
}

class _VisitHistory extends ConsumerWidget {
  const _VisitHistory({required this.patientId});
  final int patientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final visitsAsync = ref.watch(visitListProvider(patientId));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text('Visit History',
              style: Theme.of(context).textTheme.titleMedium,),
        ),
        visitsAsync.when(
          loading: () =>
              const Center(child: CircularProgressIndicator()),
          error: (e, _) => Text('Error loading visits: $e'),
          data: (visits) {
            if (visits.isEmpty) {
              return const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('No visits yet.'),
                ),
              );
            }
            return Column(
              children: visits
                  .map((v) => _VisitTile(visit: v, patientId: patientId))
                  .toList(),
            );
          },
        ),
      ],
    );
  }
}

class _VisitTile extends StatelessWidget {
  const _VisitTile({required this.visit, required this.patientId});
  final Visit visit;
  final int patientId;

  @override
  Widget build(BuildContext context) {
    final d = visit.visitDate;
    final dateStr = '${d.year}-${d.month.toString().padLeft(2, '0')}'
        '-${d.day.toString().padLeft(2, '0')}';
    return Card(
      child: ListTile(
        leading: Icon(
          visit.isComplete ? Icons.check_circle : Icons.pending,
          color: visit.isComplete ? Colors.green : Colors.orange,
        ),
        title: Text(dateStr),
        subtitle: Text(visit.chiefComplaint ?? 'No chief complaint'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () =>
            context.go('/patients/$patientId/visit/${visit.id}'),
      ),
    );
  }
}
