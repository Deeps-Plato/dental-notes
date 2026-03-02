import 'package:freezed_annotation/freezed_annotation.dart';

part 'perio_chart.freezed.dart';
part 'perio_chart.g.dart';

@freezed
class PerioReading with _$PerioReading {
  const factory PerioReading({
    required int id,
    required int chartId,
    required int toothNumber,
    required String surface, // 'buccal' | 'lingual'
    required int depthMb,
    required int depthB,
    required int depthDb,
    required bool bop,
    required int recession,
  }) = _PerioReading;

  factory PerioReading.fromJson(Map<String, dynamic> json) =>
      _$PerioReadingFromJson(json);
}

@freezed
class PerioChart with _$PerioChart {
  const factory PerioChart({
    required int id,
    required int visitId,
    String? aapStage,
    String? aapGrade,
    double? bopPercent,
    required DateTime createdAt,
    required DateTime updatedAt,
    @Default([]) List<PerioReading> readings,
  }) = _PerioChart;

  factory PerioChart.fromJson(Map<String, dynamic> json) =>
      _$PerioChartFromJson(json);
}
