import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants.dart';
import '../../data/models/odontogram.dart';
import '../../domain/odontogram_logic.dart';

class OdontogramScreen extends ConsumerStatefulWidget {
  const OdontogramScreen({super.key, required this.visitId});

  final String visitId;

  @override
  ConsumerState<OdontogramScreen> createState() => _OdontogramScreenState();
}

class _OdontogramScreenState extends ConsumerState<OdontogramScreen> {
  final Map<int, ToothRecord> _teeth = {};

  void _onToothTap(int toothNumber) {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => _ConditionPickerSheet(
        toothNumber: toothNumber,
        current: _teeth[toothNumber],
        onSave: (record) {
          setState(() {
            _teeth[toothNumber] = record;
          });
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Odontogram'),
        actions: [
          TextButton.icon(
            onPressed: _teeth.isEmpty
                ? null
                : () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          '${_teeth.length} teeth recorded for this visit.',
                        ),
                      ),
                    );
                    Navigator.of(context).pop();
                  },
            icon: const Icon(Icons.save),
            label: const Text('Save'),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  children: [
                    _ToothRow(
                      teeth: ToothNumbering.upper,
                      records: _teeth,
                      onTap: _onToothTap,
                      label: 'Upper',
                    ),
                    const SizedBox(height: 16),
                    _ToothRow(
                      teeth: ToothNumbering.lower,
                      records: _teeth,
                      onTap: _onToothTap,
                      label: 'Lower',
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (_teeth.isNotEmpty)
            _CdtCodeBar(teeth: _teeth),
        ],
      ),
    );
  }
}

class _ToothRow extends StatelessWidget {
  const _ToothRow({
    required this.teeth,
    required this.records,
    required this.onTap,
    required this.label,
  });

  final List<int> teeth;
  final Map<int, ToothRecord> records;
  final void Function(int) onTap;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          child: Text(label, style: Theme.of(context).textTheme.labelSmall),
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: teeth.map((t) => ToothWidget(
              toothNumber: t,
              record: records[t],
              onTap: () => onTap(t),
            ),).toList(),
          ),
        ),
      ],
    );
  }
}

/// A single tooth rendered as a pentagon via CustomPainter.
class ToothWidget extends StatelessWidget {
  const ToothWidget({
    super.key,
    required this.toothNumber,
    required this.onTap,
    this.record,
  });

  final int toothNumber;
  final ToothRecord? record;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.all(2),
        child: Column(
          children: [
            Text('#$toothNumber', style: const TextStyle(fontSize: 9)),
            SizedBox(
              width: 40,
              height: 40,
              child: CustomPaint(
                painter: _ToothPainter(record: record),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ToothPainter extends CustomPainter {
  const _ToothPainter({this.record});
  final ToothRecord? record;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final cx = w / 2;
    final cy = h / 2;

    // Draw 5 triangular surfaces from center outward
    final surfaces = [
      (ToothSurface.occlusal, _surfaceRect(cx, cy, 0.35, 0)), // top
      (ToothSurface.facial,   _surfaceRect(cx, cy, 0.35, 1)), // right
      (ToothSurface.distal,   _surfaceRect(cx, cy, 0.35, 2)), // bottom-right
      (ToothSurface.mesial,   _surfaceRect(cx, cy, 0.35, 3)), // bottom-left
      (ToothSurface.lingual,  _surfaceRect(cx, cy, 0.35, 4)), // left
    ];

    for (final (surface, points) in surfaces) {
      final condition = record?.surfaces
          .where((s) => s.surface == surface)
          .firstOrNull
          ?.condition;
      final paint = Paint()
        ..color = _colorFor(condition)
        ..style = PaintingStyle.fill;
      final border = Paint()
        ..color = Colors.grey.shade400
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.5;

      final path = Path()..moveTo(cx, cy);
      for (final p in points) {
        path.lineTo(p.$1, p.$2);
      }
      path.close();
      canvas.drawPath(path, paint);
      canvas.drawPath(path, border);
    }
  }

  List<(double, double)> _surfaceRect(double cx, double cy, double r, int index) {
    // Pentagon vertices at 72° intervals starting from top
    final angle1 = (index * 72 - 90) * math.pi / 180;
    final angle2 = ((index + 1) * 72 - 90) * math.pi / 180;
    final radius = cx * 0.9;
    return [
      (cx + radius * math.cos(angle1), cy + radius * math.sin(angle1)),
      (cx + radius * math.cos(angle2), cy + radius * math.sin(angle2)),
    ];
  }

  Color _colorFor(ConditionType? condition) => switch (condition) {
    null => Colors.white,
    ConditionType.sound => Colors.white,
    ConditionType.caries => Colors.red.shade200,
    ConditionType.existingRestoration => Colors.blue.shade200,
    ConditionType.proposedRestoration => Colors.yellow.shade200,
    ConditionType.crown => Colors.purple.shade200,
    ConditionType.missing || ConditionType.extracted => Colors.grey.shade300,
    _ => Colors.orange.shade100,
  };

  @override
  bool shouldRepaint(_ToothPainter oldDelegate) => oldDelegate.record != record;
}

class _ConditionPickerSheet extends StatelessWidget {
  const _ConditionPickerSheet({
    required this.toothNumber,
    required this.onSave,
    this.current,
  });

  final int toothNumber;
  final ToothRecord? current;
  final void Function(ToothRecord) onSave;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Tooth #$toothNumber', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            children: ConditionType.values.map((c) {
              return ActionChip(
                label: Text(c.name),
                onPressed: () {
                  Navigator.pop(context);
                  onSave(
                    ToothRecord(
                      toothNumber: toothNumber,
                      surfaces: [
                        SurfaceCondition(
                          surface: ToothSurface.occlusal,
                          condition: c,
                        ),
                      ],
                    ),
                  );
                },
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

class _CdtCodeBar extends StatelessWidget {
  const _CdtCodeBar({required this.teeth});

  final Map<int, ToothRecord> teeth;

  @override
  Widget build(BuildContext context) {
    final odontogram = Odontogram(visitId: 0, teeth: teeth);
    final codes = OdontogramLogic.suggestCdtCodes(odontogram);

    return Container(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      padding: const EdgeInsets.all(8),
      child: codes.isEmpty
          ? const Text(
              'No CDT codes suggested yet.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            )
          : Wrap(
              spacing: 6,
              children: codes
                  .map(
                    (code) => Chip(
                      label: Text(code, style: const TextStyle(fontSize: 11)),
                      visualDensity: VisualDensity.compact,
                    ),
                  )
                  .toList(),
            ),
    );
  }
}
