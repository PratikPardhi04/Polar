import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/sos.dart';

/// SOS button: press AND HOLD 3 seconds to trigger. Shows progress while
/// holding; releasing early cancels. Works fully offline — the packet queues
/// as HIGH-priority and jumps ahead of routine sync events.
class SosScreen extends StatefulWidget {
  const SosScreen({super.key});

  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen> {
  final _mission = TextEditingController(text: 'FM-001');
  final _location = TextEditingController();
  final _note = TextEditingController();
  final _team = TextEditingController(text: '2 pax');
  Timer? _hold;
  double _progress = 0;
  String _msg = '';
  bool _sending = false;

  void _startHold() {
    _hold?.cancel();
    const step = Duration(milliseconds: 50);
    var elapsed = 0;
    _hold = Timer.periodic(step, (t) {
      elapsed += 50;
      if (!mounted) return t.cancel();
      setState(() => _progress = elapsed / 3000);
      if (elapsed >= 3000) {
        t.cancel();
        _trigger();
      }
    });
  }

  void _cancelHold() {
    _hold?.cancel();
    if (mounted && !_sending) setState(() => _progress = 0);
  }

  Future<void> _trigger() async {
    setState(() {
      _sending = true;
      _msg = 'Sending SOS…';
    });
    final result = await SosService.send(
      missionId: _mission.text.trim(),
      location: _location.text.trim(),
      note: _note.text.trim(),
      team: _team.text.trim(),
    );
    if (mounted) {
      setState(() {
        _sending = false;
        _progress = 0;
        _msg = result;
      });
    }
  }

  @override
  void dispose() {
    _hold?.cancel();
    _mission.dispose();
    _location.dispose();
    _note.dispose();
    _team.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Press AND HOLD the SOS button for 3 seconds.', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        Listener(
          onPointerDown: (_) => _startHold(),
          onPointerUp: (_) => _cancelHold(),
          onPointerCancel: (_) => _cancelHold(),
          child: Stack(
            alignment: Alignment.center,
            children: [
              SizedBox(
                height: 140,
                child: ElevatedButton(
                  onPressed: () {},
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.red, minimumSize: const Size.fromHeight(140)),
                  child: const Text('SOS', style: TextStyle(fontSize: 40, fontWeight: FontWeight.bold)),
                ),
              ),
              if (_progress > 0) SizedBox(height: 140, child: CircularProgressIndicator(value: _progress, color: Colors.white)),
            ],
          ),
        ),
        const SizedBox(height: 12),
        TextField(controller: _mission, decoration: const InputDecoration(labelText: 'Mission id', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _location, decoration: const InputDecoration(labelText: 'Location / GPS note', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _team, decoration: const InputDecoration(labelText: 'Team', border: OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _note, decoration: const InputDecoration(labelText: 'What happened?', border: OutlineInputBorder())),
        if (_msg.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_msg)),
      ],
    );
  }
}
