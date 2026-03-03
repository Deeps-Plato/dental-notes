import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../features/medications/medications_screen.dart';
import '../features/patients/patients_screen.dart';
import '../features/patients/patient_detail_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/visit/visit_screen.dart';
import '../features/soap_note/soap_note_screen.dart';
import '../features/perio_chart/perio_chart_screen.dart';
import '../features/odontogram/odontogram_screen.dart';
import '../features/pdf_export/pdf_preview_screen.dart';

part 'router.g.dart';

@riverpod
GoRouter router(RouterRef ref) {
  return GoRouter(
    initialLocation: '/patients',
    routes: [
      GoRoute(
        path: '/settings',
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        path: '/patients',
        builder: (context, state) => const PatientsScreen(),
        routes: [
          GoRoute(
            path: ':patientId',
            builder: (context, state) => PatientDetailScreen(
              patientId: state.pathParameters['patientId']!,
            ),
            routes: [
              GoRoute(
                path: 'visit/:visitId',
                builder: (context, state) => VisitScreen(
                  patientId: state.pathParameters['patientId']!,
                  visitId: state.pathParameters['visitId']!,
                ),
                routes: [
                  GoRoute(
                    path: 'soap',
                    builder: (context, state) => SoapNoteScreen(
                      visitId: state.pathParameters['visitId']!,
                    ),
                  ),
                  GoRoute(
                    path: 'perio',
                    builder: (context, state) => PerioChartScreen(
                      visitId: state.pathParameters['visitId']!,
                    ),
                  ),
                  GoRoute(
                    path: 'odontogram',
                    builder: (context, state) => OdontogramScreen(
                      visitId: state.pathParameters['visitId']!,
                    ),
                  ),
                  GoRoute(
                    path: 'medications',
                    builder: (context, state) => MedicationsScreen(
                      visitId: state.pathParameters['visitId']!,
                    ),
                  ),
                  GoRoute(
                    path: 'pdf',
                    builder: (context, state) => PdfPreviewScreen(
                      visitId: state.pathParameters['visitId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(child: Text('Page not found: ${state.uri}')),
    ),
  );
}
