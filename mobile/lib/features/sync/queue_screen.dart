import 'package:flutter/material.dart';

import '../../core/airplane.dart';
import '../../core/api.dart';
import '../../core/database.dart';
import '../../core/sync_event.dart';

/// Pending queue: lists PENDING events, "Sync now" uploads in order.
/// Airplane-mode ON forces everything to stay PENDING (demo path).
class QueueScreen extends StatefulWidget {
  const QueueScreen({super.key});

  @override
  State<QueueScreen> createState() => _QueueScreenState();
}

class _QueueScreenState extends State<QueueScreen> {
  List<SyncEvent> _events = [];
  String _msg = '';
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    final all = await PolarisDatabase.instance.allEvents();
    if (mounted) setState(() => _events = all);
  }

  Future<void> _syncNow() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _msg = '';
    });
    try {
      if (AirplaneMode.instance.isOffline) {
        setState(() => _msg = 'Airplane mode ON — staying PENDING.');
        return;
      }
      final pending = await PolarisDatabase.instance.pendingEvents();
      if (pending.isEmpty) {
        setState(() => _msg = 'Nothing to sync.');
        return;
      }
      for (final e in pending) {
        await PolarisDatabase.instance.markStatus(e.eventId, SyncStatus.uploading);
      }
      final acked = await SyncApi().uploadBatch(pending);
      for (final e in pending) {
        await PolarisDatabase.instance.markStatus(
          e.eventId,
          acked.contains(e.eventId) ? SyncStatus.acknowledged : SyncStatus.pending,
        );
      }
      setState(() => _msg = 'Synced ${acked.length}/${pending.length} — ACKNOWLEDGED.');
    } catch (e) {
      setState(() => _msg = 'Sync failed (offline?) — events stay PENDING: $e');
    } finally {
      await _reload();
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pending = _events.where((e) => e.syncStatus == SyncStatus.pending).length;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Chip(label: Text('$pending PENDING')),
              const SizedBox(width: 8),
              ElevatedButton(onPressed: _busy ? null : _syncNow, child: const Text('Sync now')),
            ],
          ),
        ),
        if (_msg.isNotEmpty) Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: Text(_msg)),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _reload,
            child: ListView.builder(
              itemCount: _events.length,
              itemBuilder: (_, i) {
                final e = _events[i];
                return ListTile(
                  title: Text('${e.eventType} · ${e.entityId}'),
                  subtitle: Text('${e.timestamp.toIso8601String()} · ${e.deviceId}'),
                  trailing: Chip(label: Text(e.syncStatus.wire)),
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}
