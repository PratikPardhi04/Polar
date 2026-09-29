import 'dart:math';

import 'package:sqflite/sqflite.dart';

import 'sync_event.dart';

/// Local SQLite mirror. Every write path in the app inserts a SyncEvent row;
/// Phase 3.2 uploads PENDING rows in order to POST /api/v1/sync/events.
class PolarisDatabase {
  PolarisDatabase._();
  static final PolarisDatabase instance = PolarisDatabase._();
  Database? _db;

  Future<Database> get db async {
    final existing = _db;
    if (existing != null) return existing;
    final dir = await getDatabasesPath();
    final opened = await openDatabase(
      '$dir/polaris.db',
      version: 1,
      onCreate: (d, _) async {
        await d.execute('''
          CREATE TABLE sync_events(
            event_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload TEXT NOT NULL,
            sync_status TEXT NOT NULL
          )''');
        await d.execute('CREATE INDEX idx_sync_status ON sync_events(sync_status)');
        await d.execute('''
          CREATE TABLE personnel_cache(
            id TEXT PRIMARY KEY, full_name TEXT NOT NULL,
            readiness TEXT NOT NULL, role TEXT NOT NULL)''');
        await d.execute('''
          CREATE TABLE cargo_cache(
            package_id TEXT PRIMARY KEY, description TEXT NOT NULL,
            status TEXT NOT NULL, location TEXT NOT NULL)''');
        await d.execute('''
          CREATE TABLE inventory_cache(
            item_id TEXT PRIMARY KEY, name TEXT NOT NULL,
            quantity REAL NOT NULL, unit TEXT NOT NULL)''');
        await d.execute('''
          CREATE TABLE checkins(
            id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
            note TEXT NOT NULL, created_at TEXT NOT NULL)''');
      },
    );
    _db = opened;
    return opened;
  }

  String newEventId() =>
      '${DateTime.now().toUtc().millisecondsSinceEpoch}-${Random().nextInt(1 << 32)}';

  Future<void> insertEvent(SyncEvent e) async {
    final d = await db;
    await d.insert('sync_events', e.toMap());
  }

  Future<List<SyncEvent>> pendingEvents({int limit = 100}) async {
    final d = await db;
    // SOS jumps the queue: HIGH-priority emergency packets upload first.
    final rows = await d.query(
      'sync_events',
      where: 'sync_status = ?',
      whereArgs: [SyncStatus.pending.wire],
      orderBy: "CASE event_type WHEN 'SOS' THEN 0 ELSE 1 END, timestamp ASC",
      limit: limit,
    );
    return rows.map(SyncEvent.fromMap).toList();
  }

  Future<List<SyncEvent>> allEvents({int limit = 200}) async {
    final d = await db;
    final rows = await d.query('sync_events', orderBy: 'timestamp DESC', limit: limit);
    return rows.map(SyncEvent.fromMap).toList();
  }

  Future<int> countByStatus(SyncStatus s) async {
    final d = await db;
    final rows = await d.rawQuery(
      'SELECT COUNT(*) AS n FROM sync_events WHERE sync_status = ?',
      [s.wire],
    );
    return (rows.first['n'] as int?) ?? 0;
  }

  Future<void> markStatus(String eventId, SyncStatus s) async {
    final d = await db;
    await d.update(
      'sync_events',
      {'sync_status': s.wire},
      where: 'event_id = ?',
      whereArgs: [eventId],
    );
  }

  Future<void> upsertCargoCache(String packageId, String description, String status, String location) async {
    final d = await db;
    await d.rawInsert(
      'INSERT OR REPLACE INTO cargo_cache(package_id, description, status, location) VALUES(?,?,?,?)',
      [packageId, description, status, location],
    );
  }
}
