import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/models/patient.dart';

class PatientsScreen extends ConsumerWidget {
  const PatientsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Patients'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // TODO: showSearch
            },
          ),
        ],
      ),
      body: const _PatientList(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showAddPatientDialog(context),
        icon: const Icon(Icons.person_add),
        label: const Text('New Patient'),
      ),
    );
  }

  void _showAddPatientDialog(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (ctx) => const _AddPatientDialog(),
    );
  }
}

class _PatientList extends ConsumerWidget {
  const _PatientList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // TODO: wire to PatientRepository provider
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        spacing: 16,
        children: [
          Icon(Icons.people_outline, size: 64, color: Colors.grey),
          Text('No patients yet.\nTap + to add your first patient.', textAlign: TextAlign.center),
        ],
      ),
    );
  }
}

class PatientListTile extends StatelessWidget {
  const PatientListTile({super.key, required this.patient});

  final Patient patient;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: CircleAvatar(
        child: Text(patient.firstName[0] + patient.lastName[0]),
      ),
      title: Text('${patient.firstName} ${patient.lastName}'),
      subtitle: Text(
        'DOB: ${patient.dateOfBirth.year}-'
        '${patient.dateOfBirth.month.toString().padLeft(2, '0')}-'
        '${patient.dateOfBirth.day.toString().padLeft(2, '0')}',
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => context.go('/patients/${patient.id}'),
    );
  }
}

class _AddPatientDialog extends StatefulWidget {
  const _AddPatientDialog();

  @override
  State<_AddPatientDialog> createState() => _AddPatientDialogState();
}

class _AddPatientDialogState extends State<_AddPatientDialog> {
  final _formKey = GlobalKey<FormState>();
  final _firstNameCtrl = TextEditingController();
  final _lastNameCtrl = TextEditingController();
  DateTime? _dob;

  @override
  void dispose() {
    _firstNameCtrl.dispose();
    _lastNameCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Patient'),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          spacing: 12,
          children: [
            TextFormField(
              controller: _firstNameCtrl,
              decoration: const InputDecoration(labelText: 'First Name'),
              validator: (v) => (v?.isEmpty ?? true) ? 'Required' : null,
            ),
            TextFormField(
              controller: _lastNameCtrl,
              decoration: const InputDecoration(labelText: 'Last Name'),
              validator: (v) => (v?.isEmpty ?? true) ? 'Required' : null,
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                _dob == null
                    ? 'Select Date of Birth'
                    : 'DOB: ${_dob!.year}-${_dob!.month.toString().padLeft(2, '0')}-${_dob!.day.toString().padLeft(2, '0')}',
              ),
              trailing: const Icon(Icons.calendar_today),
              onTap: () async {
                final picked = await showDatePicker(
                  context: context,
                  initialDate: DateTime(1980),
                  firstDate: DateTime(1900),
                  lastDate: DateTime.now(),
                );
                if (picked != null) setState(() => _dob = picked);
              },
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
            if (_formKey.currentState!.validate() && _dob != null) {
              // TODO: save via PatientRepository
              Navigator.pop(context);
            }
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
