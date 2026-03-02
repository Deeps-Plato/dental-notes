import 'dart:typed_data';

import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

/// Generates PDF documents for dental visits.
class PdfGenerator {
  PdfGenerator._();

  /// Placeholder PDF shown in the preview screen until visit data is wired.
  static Future<Uint8List> generatePlaceholder() async {
    final doc = pw.Document();
    doc.addPage(
      pw.Page(
        pageFormat: PdfPageFormat.letter,
        build: (ctx) => pw.Center(
          child: pw.Text(
            'PDF generation — wire visit data to enable full export.',
            style: const pw.TextStyle(fontSize: 14),
          ),
        ),
      ),
    );
    return doc.save();
  }

  // TODO: generateVisitPdf(Visit, SoapNote, PerioChart, Odontogram) → Uint8List
  // Page 1: SOAP note
  // Page 2: Periodontal chart table
  // Page 3: Odontogram vector
  // Page 4: Medication changes
}
