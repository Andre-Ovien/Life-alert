import 'package:flutter/material.dart';
import 'navigation/preview_router.dart';

class LifeAlertApp extends StatefulWidget {
  const LifeAlertApp({super.key, this.router});
  final PreviewRouter? router;
  @override
  State<LifeAlertApp> createState() => _LifeAlertAppState();
}

class _LifeAlertAppState extends State<LifeAlertApp> {
  late final PreviewRouter _router = widget.router ?? PreviewRouter();
  @override
  void dispose() {
    if (widget.router == null) _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp.router(
    title: 'Life alert - non-operational preview',
    theme: ThemeData(
      colorSchemeSeed: const Color(0xFF126B67),
      useMaterial3: true,
    ),
    routerDelegate: _router,
    routeInformationParser: const PreviewPathParser(),
    debugShowCheckedModeBanner: false,
  );
}
