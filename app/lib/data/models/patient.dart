import 'package:freezed_annotation/freezed_annotation.dart';

part 'patient.freezed.dart';
part 'patient.g.dart';

@freezed
class Patient with _$Patient {
  const factory Patient({
    required int id,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    String? phone,
    String? email,
    String? allergies,
    String? medicalHistory,
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _Patient;

  factory Patient.fromJson(Map<String, dynamic> json) => _$PatientFromJson(json);
}
