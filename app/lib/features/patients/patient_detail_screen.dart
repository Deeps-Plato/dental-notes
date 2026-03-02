import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

class PatientDetailScreen extends ConsumerWidget {
  const PatientDetailScreen({super.key, required this.patientId});

  final String patientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Patient'),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit),
            onPressed: () {
              // TODO: edit patient
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // TODO: load patient from repository
          const _PatientInfoCard(),
          const SizedBox(height: 16),
          const _VisitHistory(),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _startNewVisit(context),
        icon: const Icon(Icons.add_circle_outline),
        label: const Text('New Visit'),
      ),
    );
  }

  void _startNewVisit(BuildContext context) {
    // TODO: create visit in DB then navigate
    context.go('/patients/$patientId/visit/new');
  }
}

class _PatientInfoCard extends StatelessWidget {
  const _PatientInfoCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 8,
          children: [
            Text('Patient Info', style: Theme.of(context).textTheme.titleMedium),
            // TODO: populate from provider
            const Text('Loading…'),
          ],
        ),
      ),
    );
  }
}

class _VisitHistory extends StatelessWidget {
  const _VisitHistory();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text('Visit History', style: Theme.of(context).textTheme.titleMedium),
        ),
        // TODO: load visits from repository
        const Center(child: Text('No visits yet.')),
      ],
    );
  }
}
