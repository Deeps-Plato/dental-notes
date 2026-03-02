import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:printing/printing.dart';

import '../../domain/pdf_generator.dart';

class PdfPreviewScreen extends ConsumerWidget {
  const PdfPreviewScreen({super.key, required this.visitId});

  final String visitId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Export PDF'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share),
            tooltip: 'Share PDF',
            onPressed: () {
              // TODO: share via printing package
            },
          ),
          IconButton(
            icon: const Icon(Icons.download),
            tooltip: 'Save to files',
            onPressed: () {
              // TODO: save to device
            },
          ),
        ],
      ),
      body: PdfPreview(
        build: (format) async {
          // TODO: load visit data from repository and generate PDF
          return PdfGenerator.generatePlaceholder();
        },
        allowPrinting: true,
        allowSharing: true,
      ),
    );
  }
}
