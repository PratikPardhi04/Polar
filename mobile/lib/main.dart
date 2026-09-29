import 'package:flutter/material.dart';

import 'core/airplane.dart';
import 'core/database.dart';
import 'core/sync_event.dart';
import 'features/checkin/checkin_screen.dart';
import 'features/inventory/inventory_screen.dart';
import 'features/personnel/personnel_screen.dart';
import 'features/scanner/qr_scanner_screen.dart';
import 'features/sos/sos_screen.dart';
import 'features/sync/queue_screen.dart';

void main() => runApp(const PolarisApp());

class PolarisApp extends StatefulWidget {
  const PolarisApp({super.key});

  @override
  State<PolarisApp> createState() => _PolarisAppState();
}

class _PolarisAppState extends State<PolarisApp> {
  int _tab = 0;
  int _pending = 0;

  static const _screens = [
    QrScannerScreen(),
    QueueScreen(),
    InventoryScreen(),
    CheckinScreen(),
    PersonnelScreen(),
  ];

  @override
  void initState() {
    super.initState();
    _refreshBadge();
    AirplaneMode.instance.offline.addListener(_refreshBadge);
  }

  Future<void> _refreshBadge() async {
    final n = await PolarisDatabase.instance.countByStatus(SyncStatus.pending);
    if (mounted) setState(() => _pending = n);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'POLARIS Field',
      theme: ThemeData.dark(),
      home: Scaffold(
        appBar: AppBar(
          title: const Text('POLARIS Field — EXP-46ISEA-2026'),
          actions: [
            Builder(
              builder: (ctx) => TextButton(
                onPressed: () => Navigator.of(ctx).push(MaterialPageRoute(builder: (_) => const SosScreen())),
                style: TextButton.styleFrom(backgroundColor: Colors.red, foregroundColor: Colors.white),
                child: const Text('SOS', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
            Row(
              children: [
                const Text('Airplane'),
                ValueListenableBuilder<bool>(
                  valueListenable: AirplaneMode.instance.offline,
                  builder: (_, offline, __) => Switch(
                    value: offline,
                    onChanged: (v) {
                      AirplaneMode.instance.setOffline(v);
                      _refreshBadge();
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
        body: _screens[_tab],
        bottomNavigationBar: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) {
            setState(() => _tab = i);
            _refreshBadge();
          },
          destinations: [
            const NavigationDestination(icon: Icon(Icons.qr_code_scanner), label: 'Scan'),
            NavigationDestination(icon: Badge(label: Text('$_pending'), child: const Icon(Icons.sync)), label: 'Queue'),
            const NavigationDestination(icon: Icon(Icons.inventory), label: 'Issue'),
            const NavigationDestination(icon: Icon(Icons.check), label: 'Check-in'),
            const NavigationDestination(icon: Icon(Icons.people), label: 'Team'),
          ],
        ),
      ),
    );
  }
}
