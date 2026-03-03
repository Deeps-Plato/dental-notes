import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/database/app_database.dart';
import '../../data/repositories/patient_repository.dart';

part 'patients_notifier.g.dart';

/// Watches all patients as a live stream.
@riverpod
Stream<List<Patient>> patientList(PatientListRef ref) {
  final repo = ref.watch(patientRepositoryProvider);
  return repo.watchAll();
}

/// Watches a single patient by ID.
@riverpod
Stream<Patient?> patientDetail(PatientDetailRef ref, int patientId) {
  final repo = ref.watch(patientRepositoryProvider);
  return repo.watchById(patientId);
}

/// Watches patients matching a search query.
@riverpod
Stream<List<Patient>> patientSearch(PatientSearchRef ref, String query) {
  if (query.isEmpty) {
    final repo = ref.watch(patientRepositoryProvider);
    return repo.watchAll();
  }
  final repo = ref.watch(patientRepositoryProvider);
  return repo.watchSearch(query);
}

/// Actions (create/update/delete) — imperative calls, not watched.
@riverpod
PatientActions patientActions(PatientActionsRef ref) {
  final repo = ref.watch(patientRepositoryProvider);
  return PatientActions(repo);
}

class PatientActions {
  PatientActions(this._repo);
  final PatientRepository _repo;

  Future<int> create({
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    String? phone,
    String? email,
    String? allergies,
    String? medicalHistory,
  }) => _repo.create(
    firstName: firstName,
    lastName: lastName,
    dateOfBirth: dateOfBirth,
    phone: phone,
    email: email,
    allergies: allergies,
    medicalHistory: medicalHistory,
  );

  Future<void> delete(int id) => _repo.delete(id);
}
