import 'package:flutter/material.dart';
import '../../app/navigation/screen_spec.dart';

class ScreenPlaceholder extends StatelessWidget {
  const ScreenPlaceholder({super.key, required this.screen});
  final ScreenSpec screen;
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(20),
    children: [
      Text(
        '${screen.id} - ${screen.title}',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 12),
      const Text(
        'STRUCTURE ONLY. This screen has no functioning product actions.',
      ),
      const Divider(height: 32),
      _section('Purpose', screen.purpose),
      _section('Planned content and actions', screen.actions),
      _section('Required variants', screen.states),
      _section('Current integration boundary', screen.apiBoundary),
      _section(
        'Proposed route / design phase',
        '${screen.path} / ${screen.phase}',
      ),
      const Text(
        'No alert, call, payment, identity verification or child data is handled here.',
      ),
    ],
  );
  Widget _section(String title, String value) => Padding(
    padding: const EdgeInsets.only(bottom: 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        Text(value),
      ],
    ),
  );
}
