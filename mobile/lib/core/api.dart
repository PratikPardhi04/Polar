import 'dart:convert';
import 'dart:io';

import 'sync_event.dart';

/// Minimal backend client (dart:io only — no extra pub deps).
/// Upload lands server-side in Phase 3.2 (POST /api/v1/sync/events batch).
class SyncApi {
  final String baseUrl;
  final String bearerToken;
  final HttpClient _http = HttpClient();

  SyncApi({this.baseUrl = 'http://10.0.2.2:8000', this.bearerToken = ''});

  Future<Set<String>> uploadBatch(List<SyncEvent> events) async {
    final req = await _http.postUrl(Uri.parse('$baseUrl/api/v1/sync/events'));
    req.headers.contentType = ContentType.json;
    if (bearerToken.isNotEmpty) req.headers.set('Authorization', 'Bearer $bearerToken');
    req.write(jsonEncode({'events': events.map((e) => e.toWire()).toList()}));
    final res = await req.close();
    final body = await res.transform(utf8.decoder).join();
    if (res.statusCode != 200) throw HttpException('sync failed ${res.statusCode}: $body');
    final decoded = jsonDecode(body) as Map<String, dynamic>;
    final acked = (decoded['acknowledged'] as List?) ?? const [];
    return acked.map((e) => e.toString()).toSet();
  }
}
