import 'package:flutter/material.dart';

import '../../core/database.dart';
import '../../core/sync_event.dart';

/// Field check-in: queues a FIELD_CHECK_IN SyncEvent locally. The due/grace/
/// missed pipeline runs server-side in Phase 4.3; the app only guarantees
/// capture with no network required.
class CheckinScreen extends StatefulWidget {
  const CheckinScreen({super.key});

  @override
  State<CheckinScreen> createState() => _CheckinScreenState();
}

class _CheckinScreenState extends State<CheckinScreen> {
  final _mission = TextEditingController(text: 'FM-001');
  final _note = TextEditingController();
  String _msg = '';

  Future<void> _save() async {
    if (_mission.text.trim().isEmpty) {
      setState(() => _msg = 'Enter a mission id.');
      return;
    }
    final event = SyncEvent(
      eventId: PolarisDatabase.instance.newEventId(),
      deviceId: 'FIELD-TABLET-01',
      userId: 'field-user',
      eventType: EventTypes.fieldCheckIn,
      entityId: _mission.text.trim(),
      timestamp: DateTime.now().toUtc(),
      payload: {'mission_id': _mission.text.trim(), 'note': _note.text.trim()},
    );
    await PolarisDatabase.instance.insertEvent(event);
    final d = await PolarisDatabase.instance.db;
    await d.rawInsert(
      'INSERT OR REPLACE INTO checkins(id, mission_id, note, created_at) VALUES(?,?,?,?)',
      [event.eventId, _mission.text.trim(), _note.text.trim(), event.timestamp.toIso8601String()],
    );
    setState(() => _msg = 'Saved locally — SYNC: PENDING');
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(controller: _mission, decoration: const InputDecoration(labelText: 'Mission id', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note (optional)', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        ElevatedButton(onPressed: _save, child: const Text('Check in offline')),
        if (_msg.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_msg)),
      ],
    );
  }
}
