import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';

/// Wraps the app and requires biometric/PIN authentication.
///
/// Re-locks after [lockTimeout] in the background. Shows a blurred lock
/// screen so PHI is hidden in the app switcher.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key, required this.child});

  final Widget child;

  /// Time in background before re-authentication is required.
  static const lockTimeout = Duration(minutes: 5);

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> with WidgetsBindingObserver {
  final _auth = LocalAuthentication();
  bool _isLocked = true;
  bool _isAuthenticating = false;
  DateTime? _backgroundedAt;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Authenticate on first launch.
    WidgetsBinding.instance.addPostFrameCallback((_) => _authenticate());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.paused:
      case AppLifecycleState.hidden:
        _backgroundedAt = DateTime.now();
        // Immediately show lock screen so PHI is hidden in app switcher.
        setState(() => _isLocked = true);
      case AppLifecycleState.resumed:
        if (_backgroundedAt != null) {
          final elapsed = DateTime.now().difference(_backgroundedAt!);
          if (elapsed >= AuthGate.lockTimeout) {
            // Timed out — require re-auth.
            _authenticate();
          } else {
            // Quick return — unlock without re-auth.
            setState(() => _isLocked = false);
          }
          _backgroundedAt = null;
        }
      default:
        break;
    }
  }

  Future<void> _authenticate() async {
    if (_isAuthenticating) return;
    _isAuthenticating = true;

    try {
      final canAuth = await _auth.canCheckBiometrics || await _auth.isDeviceSupported();
      if (!canAuth) {
        // No biometric or device auth available — allow through.
        setState(() => _isLocked = false);
        return;
      }

      final success = await _auth.authenticate(
        localizedReason: 'Authenticate to access Dental Notes',
        options: const AuthenticationOptions(
          stickyAuth: true,
          biometricOnly: false,
        ),
      );

      if (success) {
        setState(() => _isLocked = false);
      }
    } catch (_) {
      // Auth failed or cancelled — stay locked.
    } finally {
      _isAuthenticating = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLocked) {
      return _LockScreen(onUnlock: _authenticate);
    }
    return widget.child;
  }
}

class _LockScreen extends StatelessWidget {
  const _LockScreen({required this.onUnlock});

  final VoidCallback onUnlock;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            spacing: 24,
            children: [
              Icon(
                Icons.lock_outline,
                size: 64,
                color: Theme.of(context).colorScheme.primary,
              ),
              Text(
                'Dental Notes',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Text(
                'Authenticate to continue',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              FilledButton.icon(
                onPressed: onUnlock,
                icon: const Icon(Icons.fingerprint),
                label: const Text('Unlock'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
