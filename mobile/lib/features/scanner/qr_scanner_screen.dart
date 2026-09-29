import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../core/airplane.dart';
import '../../core/database.dart';
import '../../core/sync_event.dart';

/// QR scanner: works with zero connectivity. Every scan appends a
/// CARGO_SCANNED SyncEvent (PENDING) and caches the package locally.
class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key});

  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen> {
  final _manual = TextEditingController();
  String _last = '';
  String _banner = '';
  bool _busy = false;
  final _scanner = MobileScannerController();

  @override
  void dispose() {
    _manual.dispose();
    _scanner.dispose();
    super.dispose();
  }

  String _resolvePackageId(String raw) {
    final v = raw.trim();
    if (v.startsWith('POLARIS:')) return v.split('POLARIS:').last.trim();
    return v;
  }

  Future<void> _saveScan(String raw) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _banner = '';
    });
    try {
      final packageId = _resolvePackageId(raw);
      if (packageId.isEmpty) throw StateError('empty QR payload');
      final event = SyncEvent(
        eventId: PolarisDatabase.instance.newEventId(),
        deviceId: 'FIELD-TABLET-01',
        userId: 'field-user',
        eventType: EventTypes.cargoScanned,
        entityId: packageId,
        timestamp: DateTime.now().toUtc(),
        payload: {'raw': raw, 'package_id': packageId, 'location': 'field'},
      );
      await PolarisDatabase.instance.insertEvent(event);
      await PolarisDatabase.instance.upsertCargoCache(packageId, '', 'SCANNED', 'field');
      setState(() {
        _last = packageId;
        _banner = 'Saved locally — SYNC: PENDING';
      });
    } catch (e) {
      setState(() => _banner = 'Scan failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ValueListenableBuilder<bool>(
          valueListenable: AirplaneMode.instance.offline,
          builder: (_, offline, __) => Chip(
            label: Text(offline ? 'OFFLINE — queueing locally' : 'ONLINE'),
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 280,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: MobileScanner(
              controller: _scanner,
              onDetect: (capture) {
                final raw = capture.barcodes.firstOrNull?.rawValue;
                if (raw != null && raw.isNotEmpty) _saveScan(raw);
              },
            ),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _manual,
          decoration: const InputDecoration(
            labelText: 'Manual package id (e.g. BX-46-2026-000001)',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        ElevatedButton(
          onPressed: _busy ? null : () => _saveScan(_manual.text),
          child: const Text('Save scan offline'),
        ),
        const SizedBox(height: 12),
        if (_last.isNotEmpty) Text('Last: $_last', style: const TextStyle(fontWeight: FontWeight.bold)),
        if (_banner.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(_banner, style: TextStyle(color: _banner.startsWith('Saved') ? Colors.green : Colors.red)),
          ),
      ],
    );
  }
}
