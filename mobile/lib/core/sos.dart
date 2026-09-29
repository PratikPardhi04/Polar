import 'airplane.dart';
import 'api.dart';
import 'database.dart';
import 'sync_event.dart';

/// Offline emergency packet sender. The packet carries identity, GPS
/// (SIMULATED — real GPS is a stretch goal), mission, team, expected return,
/// battery (SIMULATED), and comm status. Stored as a HIGH-priority SOS
/// SyncEvent that jumps the queue; best-effort immediate upload when online.
class SosService {
  static Future<String> send({
    String personnelId = '',
    String missionId = '',
    String location = '',
    String note = '',
    String team = '',
    String expectedReturn = '',
    String batteryPct = '70',
  }) async {
    final offline = AirplaneMode.instance.isOffline;
    final packet = {
      'personnel_id': personnelId,
      'mission_id': missionId,
      'location': location.isEmpty ? 'SIMULATED-GPS 69.41S 76.19E (Bharati vicinity)' : location,
      'note': note,
      'team': team,
      'expected_return': expectedReturn,
      'battery_pct': int.tryParse(batteryPct) ?? 70,
      'battery_simulated': true,
      'comm_status': offline ? 'offline-airplane-mode' : 'weak-iridium',
      'gps_simulated': true,
      'priority': 'HIGH',
    };
    final event = SyncEvent(
      eventId: PolarisDatabase.instance.newEventId(),
      deviceId: 'FIELD-TABLET-01',
      userId: 'field-user',
      eventType: EventTypes.sos,
      entityId: missionId.isEmpty ? 'SOS' : missionId,
      timestamp: DateTime.now().toUtc(),
      payload: packet,
    );
    await PolarisDatabase.instance.insertEvent(event);
    if (!offline) {
      try {
        final acked = await SyncApi().uploadBatch([event]);
        if (acked.contains(event.eventId)) {
          await PolarisDatabase.instance.markStatus(event.eventId, SyncStatus.acknowledged);
          return 'SOS sent — ACKNOWLEDGED by command centre.';
        }
      } catch (_) {
        // stays PENDING; aggressive retry happens on every Queue visit + Sync now
      }
    }
    return 'SOS saved locally — SYNC: PENDING (will retry aggressively).';
  }
}
