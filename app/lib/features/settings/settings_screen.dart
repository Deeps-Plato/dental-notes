import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _baseUrlKey = 'backend_base_url';
const _apiKeyKey = 'backend_api_key';
const _defaultBaseUrl = 'http://localhost:8765';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _storage = const FlutterSecureStorage();
  final _urlCtrl = TextEditingController();
  final _keyCtrl = TextEditingController();
  bool _isLoading = true;
  bool _isSaving = false;
  bool _obscureKey = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final url = await _storage.read(key: _baseUrlKey) ?? _defaultBaseUrl;
    final key = await _storage.read(key: _apiKeyKey) ?? '';
    _urlCtrl.text = url;
    _keyCtrl.text = key;
    setState(() => _isLoading = false);
  }

  Future<void> _save() async {
    setState(() => _isSaving = true);
    await _storage.write(key: _baseUrlKey, value: _urlCtrl.text.trim());
    await _storage.write(key: _apiKeyKey, value: _keyCtrl.text.trim());
    setState(() => _isSaving = false);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Settings saved. Restart app to apply.')),
      );
    }
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    _keyCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  'Backend Connection',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _urlCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Backend URL',
                    hintText: 'https://abc123.ngrok-free.app',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.dns),
                  ),
                  keyboardType: TextInputType.url,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _keyCtrl,
                  decoration: InputDecoration(
                    labelText: 'API Key',
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.key),
                    suffixIcon: IconButton(
                      icon: Icon(
                        _obscureKey ? Icons.visibility_off : Icons.visibility,
                      ),
                      onPressed: () =>
                          setState(() => _obscureKey = !_obscureKey),
                    ),
                  ),
                  obscureText: _obscureKey,
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: _isSaving ? null : _save,
                  icon: _isSaving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.save),
                  label: const Text('Save'),
                ),
                const SizedBox(height: 32),
                const Divider(),
                const SizedBox(height: 16),
                Text(
                  'About',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                const ListTile(
                  leading: Icon(Icons.info_outline),
                  title: Text('Dental Notes'),
                  subtitle: Text('v0.1.0 — HIPAA-aligned dental note-taking'),
                ),
                const ListTile(
                  leading: Icon(Icons.security),
                  title: Text('Data Storage'),
                  subtitle: Text(
                    'All patient data is encrypted on-device with AES-256.\n'
                    'Audio is transcribed and immediately deleted.\n'
                    'No patient data is stored on the server.',
                  ),
                ),
              ],
            ),
    );
  }
}
