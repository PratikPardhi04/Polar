import 'package:flutter/material.dart';

import '../../core/database.dart';
import '../../core/sync_event.dart';

/// Offline inventory ISSUE: validates nothing locally (server is the source of
/// truth) — the event goes PENDING; Phase 3.2 conflict detection resolves
/// over-issue on reconnect ("ACTION REQUIRED" on the dashboard).
class InventoryScreen extends StatefulWidget {
  const InventoryScreen({super.key});

  @override
  State<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends State<InventoryScreen> {
  final _item = TextEditingController(text: 'Diesel (polar)');
  final _qty = TextEditingController(text: '20');
  String _msg = '';

  Future<void> _save() async {
    final qty = double.tryParse(_qty.text) ?? -1;
    if (_item.text.trim().isEmpty || qty <= 0) {
      setState(() => _msg = 'Enter an item and a positive quantity.');
      return;
    }
    final event = SyncEvent(
      eventId: PolarisDatabase.instance.newEventId(),
      deviceId: 'FIELD-TABLET-01',
      userId: 'field-user',
      eventType: EventTypes.inventoryIssue,
      entityId: _item.text.trim(),
      timestamp: DateTime.now().toUtc(),
      payload: {'item': _item.text.trim(), 'quantity': qty, 'unit': 'L'},
    );
    await PolarisDatabase.instance.insertEvent(event);
    setState(() => _msg = 'Saved locally — SYNC: PENDING');
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(controller: _item, decoration: const InputDecoration(labelText: 'Item', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _qty, decoration: const InputDecoration(labelText: 'Quantity', border: OutlineInputBorder()), keyboardType: TextInputType.number),
        const SizedBox(height: 8),
        ElevatedButton(onPressed: _save, child: const Text('Issue offline')),
        if (_msg.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_msg)),
      ],
    );
  }
}
