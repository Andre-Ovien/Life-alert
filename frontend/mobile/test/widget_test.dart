import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:life_alert_mobile/app/life_alert_app.dart';
import 'package:life_alert_mobile/app/navigation/preview_router.dart';
import 'package:life_alert_mobile/core/access/preview_session.dart';

void main() {
  testWidgets('preview labels are persistent and a parent placeholder opens', (
    tester,
  ) async {
    final router = PreviewRouter(
      session: const PreviewSession(role: PreviewRole.guardian),
    );
    await tester.pumpWidget(LifeAlertApp(router: router));
    await tester.pumpAndSettle();
    router.open(Uri.parse('/home'));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('No help requests, calls, payments'),
      findsOneWidget,
    );
    expect(find.text('G01 - Family home'), findsOneWidget);
    expect(
      find.text(
        'STRUCTURE ONLY. This screen has no functioning product actions.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('child goes straight to child home without an adult sign in', (
    tester,
  ) async {
    final router = PreviewRouter();
    await tester.pumpWidget(LifeAlertApp(router: router));
    await tester.pumpAndSettle();
    router.setSession(const PreviewSession(role: PreviewRole.linkedChild));
    await tester.pumpAndSettle();
    expect(find.text('C02 - Accessible child help home'), findsOneWidget);
    expect(find.text('A02 - Adult sign in'), findsNothing);
    router.open(Uri.parse('/subscription'));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('access-denied')), findsOneWidget);
    expect(find.text('B01 - Subscription + entitlement'), findsNothing);
  });

  testWidgets('role change clears previously visible parent route', (
    tester,
  ) async {
    final router = PreviewRouter(
      session: const PreviewSession(role: PreviewRole.guardian),
    );
    await tester.pumpWidget(LifeAlertApp(router: router));
    await tester.pumpAndSettle();
    router.open(Uri.parse('/children/preview-child'));
    await tester.pumpAndSettle();
    expect(find.text('F02 - Child overview'), findsOneWidget);
    router.setSession(const PreviewSession(role: PreviewRole.linkedChild));
    await tester.pumpAndSettle();
    expect(find.text('F02 - Child overview'), findsNothing);
    expect(find.text('C02 - Accessible child help home'), findsOneWidget);
  });

  testWidgets('large text on a narrow device has no layout exception', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 740);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final router = PreviewRouter();
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.8)),
        child: LifeAlertApp(router: router),
      ),
    );
    await tester.pumpAndSettle();
    router.open(Uri.parse('/access/sign-in'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
