import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/database/app_database.dart';
import 'patients_notifier.dart';

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
              // TODO: showSearch delegate
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
    final patientsAsync = ref.watch(patientListProvider);

    return patientsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (patients) {
        if (patients.isEmpty) {
          return const Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              spacing: 16,
              children: [
                Icon(Icons.people_outline, size: 64, color: Colors.grey),
                Text(
                  'No patients yet.\nTap + to add your first patient.',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          );
        }
        return ListView.builder(
          itemCount: patients.length,
          itemBuilder: (context, index) =>
              _PatientListTile(patient: patients[index]),
        );
      },
    );
  }
}

class _PatientListTile extends StatelessWidget {
  const _PatientListTile({required this.patient});

  final Patient patient;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: CircleAvatar(
        child: Text(
          '${patient.firstName[0]}${patient.lastName[0]}'.toUpperCase(),
        ),
      ),
      title: Text('${patient.lastName}, ${patient.firstName}'),
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

class _AddPatientDialog extends ConsumerStatefulWidget {
  const _AddPatientDialog();

  @override
  ConsumerState<_AddPatientDialog> createState() => _AddPatientDialogState();
}

class _AddPatientDialogState extends ConsumerState<_AddPatientDialog> {
  final _formKey = GlobalKey<FormState>();
  final _firstNameCtrl = TextEditingController();
  final _lastNameCtrl = TextEditingController();
  DateTime? _dob;
  bool _isSaving = false;

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
              textCapitalization: TextCapitalization.words,
              validator: (v) => (v?.isEmpty ?? true) ? 'Required' : null,
            ),
            TextFormField(
              controller: _lastNameCtrl,
              decoration: const InputDecoration(labelText: 'Last Name'),
              textCapitalization: TextCapitalization.words,
              validator: (v) => (v?.isEmpty ?? true) ? 'Required' : null,
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                _dob == null
                    ? 'Select Date of Birth'
                    : 'DOB: ${_dob!.year}-'
                        '${_dob!.month.toString().padLeft(2, '0')}-'
                        '${_dob!.day.toString().padLeft(2, '0')}',
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
        TextButton(
          onPressed: _isSaving ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _isSaving ? null : _save,
          child: _isSaving
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Save'),
        ),
      ],
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    if (_dob == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a date of birth')),
      );
      return;
    }

    setState(() => _isSaving = true);
    try {
      final actions = ref.read(patientActionsProvider);
      final id = await actions.create(
        firstName: _firstNameCtrl.text.trim(),
        lastName: _lastNameCtrl.text.trim(),
        dateOfBirth: _dob!,
      );
      if (mounted) {
        Navigator.pop(context);
        context.go('/patients/$id');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isSaving = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
      }
    }
  }
}
