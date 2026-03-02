import 'package:freezed_annotation/freezed_annotation.dart';

part 'visit.freezed.dart';
part 'visit.g.dart';

@freezed
class Visit with _$Visit {
  const factory Visit({
    required int id,
    required int patientId,
    required DateTime visitDate,
    String? chiefComplaint,
    String? provider,
    String? rawTranscript,
    required bool isComplete,
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _Visit;

  factory Visit.fromJson(Map<String, dynamic> json) => _$VisitFromJson(json);
}
