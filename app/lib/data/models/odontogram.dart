import 'package:freezed_annotation/freezed_annotation.dart';

part 'odontogram.freezed.dart';
part 'odontogram.g.dart';

enum ToothSurface { mesial, distal, occlusal, facial, lingual }

enum ConditionType {
  sound,
  caries,
  existingRestoration,
  proposedRestoration,
  crown,
  implant,
  missing,
  extracted,
  unerupted,
  fractured,
  watchArea,
}

enum RestorativeMaterial { composite, amalgam, porcelain, gold, stainlessSteel, other }

@freezed
class SurfaceCondition with _$SurfaceCondition {
  const factory SurfaceCondition({
    required ToothSurface surface,
    required ConditionType condition,
    RestorativeMaterial? material,
    String? notes,
  }) = _SurfaceCondition;

  factory SurfaceCondition.fromJson(Map<String, dynamic> json) =>
      _$SurfaceConditionFromJson(json);
}

@freezed
class ToothRecord with _$ToothRecord {
  const factory ToothRecord({
    required int toothNumber,
    required List<SurfaceCondition> surfaces,
    String? notes,
  }) = _ToothRecord;

  factory ToothRecord.fromJson(Map<String, dynamic> json) =>
      _$ToothRecordFromJson(json);
}

@freezed
class Odontogram with _$Odontogram {
  const factory Odontogram({
    required int visitId,
    required Map<int, ToothRecord> teeth,
  }) = _Odontogram;

  factory Odontogram.fromJson(Map<String, dynamic> json) =>
      _$OdontogramFromJson(json);
}
