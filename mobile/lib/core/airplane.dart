import 'package:flutter/foundation.dart';

/// Simulated connectivity for demo + field testing. Phase 3.2 wires this to
/// the real upload path; the airplane toggle lets judges see PENDING → ACKNOWLEDGED.
class AirplaneMode extends ChangeNotifier {
  AirplaneMode._();
  static final AirplaneMode instance = AirplaneMode._();

  final ValueNotifier<bool> offline = ValueNotifier<bool>(false);

  bool get isOffline => offline.value;

  void setOffline(bool v) {
    offline.value = v;
    notifyListeners();
  }
}
