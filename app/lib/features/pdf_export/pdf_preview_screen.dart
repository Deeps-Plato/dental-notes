import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:printing/printing.dart';

import '../../data/database/app_database.dart';
import '../../data/models/perio_chart.dart' as models;
import '../../data/repositories/perio_repository.dart';
import '../../data/repositories/soap_note_repository.dart';
import '../../data/repositories/visit_repository.dart';
import '../../domain/pdf_generator.dart';

class PdfPreviewScreen extends ConsumerWidget {
  const PdfPreviewScreen({super.key, required this.visitId});

  final String visitId;

  int get _visitId => int.parse(visitId);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Export PDF'),
      ),
      body: PdfPreview(
        build: (format) async {
          final visitRepo = ref.read(visitRepositoryProvider);
          final visit = await visitRepo.getById(_visitId);
          if (visit == null) return PdfGenerator.generatePlaceholder();

          final noteRepo = ref.read(soapNoteRepositoryProvider);
          final soapNote = await noteRepo.getForVisit(_visitId);

          final perioRepo = ref.read(perioRepositoryProvider);
          final chart = await perioRepo.watchChartForVisit(_visitId).first;
          final readings = chart != null
              ? await perioRepo.getReadingsForChart(chart.id)
              : <PerioReading>[];

          return PdfGenerator.generateVisitPdf(
            visit: visit,
            soapNote: soapNote,
            perioChart: chart,
            perioReadings: readings
                .map(_toModelReading)
                .toList(),
          );
        },
        allowPrinting: true,
        allowSharing: true,
        pdfFileName:
            'visit_${DateTime.now().toIso8601String().split('T').first}.pdf',
      ),
    );
  }

  static models.PerioReading _toModelReading(PerioReading row) =>
      models.PerioReading(
        id: row.id,
        chartId: row.chartId,
        toothNumber: row.toothNumber,
        surface: row.surface,
        depthMb: row.depthMb,
        depthB: row.depthB,
        depthDb: row.depthDb,
        bop: row.bop,
        recession: row.recession,
      );
}
