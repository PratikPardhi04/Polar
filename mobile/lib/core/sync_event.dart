import 'dart:convert';

/// Sync status for every local write. Mirrors the backend contract in Phase 3.2:
/// POST /api/v1/sync/events accepts PENDING events, returns ACK per event_id.
enum SyncStatus { pending, uploading, acknowledged }

extension SyncStatusX on SyncStatus {
  String get wire {
    switch (this) {
      case SyncStatus.pending:
        return 'PENDING';
      case SyncStatus.uploading:
        return 'UPLOADING';
      case SyncStatus.acknowledged:
        return 'ACKNOWLEDGED';
    }
  }

  static SyncStatus fromWire(String v) {
    switch (v) {
      case 'UPLOADING':
        return SyncStatus.uploading;
      case 'ACKNOWLEDGED':
        return SyncStatus.acknowledged;
      default:
        return SyncStatus.pending;
    }
  }
}

/// Event types written locally. SOS lands in Phase 5.2; the type is reserved here.
class EventTypes {
  static const cargoScanned = 'CARGO_SCANNED';
  static const inventoryIssue = 'INVENTORY_ISSUE';
  static const fieldCheckIn = 'FIELD_CHECK_IN';
  static const readinessNote = 'READINESS_NOTE';
  static const sos = 'SOS';
}

class SyncEvent {
  final String eventId;
  final String deviceId;
  final String userId;
  final String eventType;
  final String entityId;
  final DateTime timestamp;
  final Map<String, dynamic> payload;
  final SyncStatus syncStatus;

  const SyncEvent({
    required this.eventId,
    required this.deviceId,
    required this.userId,
    required this.eventType,
    required this.entityId,
    required this.timestamp,
    required this.payload,
    this.syncStatus = SyncStatus.pending,
  });

  Map<String, dynamic> toMap() => {
        'event_id': eventId,
        'device_id': deviceId,
        'user_id': userId,
        'event_type': eventType,
        'entity_id': entityId,
        'timestamp': timestamp.toIso8601String(),
        'payload': jsonEncode(payload),
        'sync_status': syncStatus.wire,
      };

  Map<String, dynamic> toWire() => {
        'event_id': eventId,
        'device_id': deviceId,
        'user_id': userId,
        'event_type': eventType,
        'entity_id': entityId,
        'timestamp': timestamp.toIso8601String(),
        'payload': payload,
      };

  static SyncEvent fromMap(Map<String, dynamic> m) => SyncEvent(
        eventId: m['event_id'] as String,
        deviceId: m['device_id'] as String,
        userId: m['user_id'] as String,
        eventType: m['event_type'] as String,
        entityId: m['entity_id'] as String,
        timestamp: DateTime.parse(m['timestamp'] as String),
        payload: jsonDecode(m['payload'] as String) as Map<String, dynamic>,
        syncStatus: SyncStatusX.fromWire(m['sync_status'] as String),
      );
}
