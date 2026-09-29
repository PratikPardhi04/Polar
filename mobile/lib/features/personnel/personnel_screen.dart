import 'package:flutter/material.dart';

/// Cached personnel readiness (SQLite mirror). Server remains the source of
/// truth; this list renders whatever was last cached for offline reference.
class PersonnelScreen extends StatelessWidget {
  const PersonnelScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Personnel cache — syncs from GET /api/v1/personnel in Phase 3.2.\n'
          'Readiness transitions are approved server-side only.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
