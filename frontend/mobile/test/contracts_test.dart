import 'package:flutter_test/flutter_test.dart';
import 'package:life_alert_mobile/app/navigation/catalog.dart';
import 'package:life_alert_mobile/app/navigation/route_policy.dart';
import 'package:life_alert_mobile/app/navigation/preview_router.dart';
import 'package:life_alert_mobile/core/access/preview_session.dart';
import 'package:life_alert_mobile/core/api/api_boundary.dart';
import 'package:life_alert_mobile/features/incidents/data/disabled_incident_repository.dart';
import 'package:life_alert_mobile/features/incidents/domain/help_contract.dart';

void main() {
  test('consumer inventory routes are unique and staff is excluded', () {
    expect(consumerScreens.length, 46);
    expect(consumerScreens.map((s) => s.id).toSet().length, 46);
    for (final spec in consumerScreens) {
      expect(matchScreen(Uri.parse(spec.previewPath()))?.screen.id, spec.id);
      expect(spec.phase, isNot('O'));
    }
    expect(matchScreen(Uri.parse('/ops/incidents')), isNull);
  });
  test('signed out, child and limited caregiver scopes are enforced', () {
    final parent = matchScreen(Uri.parse('/home'))!;
    final child = matchScreen(Uri.parse('/child/home'))!;
    expect(canOpen(const PreviewSession(), parent), isFalse);
    expect(
      canOpen(const PreviewSession(role: PreviewRole.linkedChild), parent),
      isFalse,
    );
    expect(
      canOpen(const PreviewSession(role: PreviewRole.linkedChild), child),
      isTrue,
    );
    expect(
      canOpen(
        const PreviewSession(role: PreviewRole.caregiver),
        matchScreen(Uri.parse('/household/invite'))!,
      ),
      isFalse,
    );
    expect(
      canOpen(
        const PreviewSession(role: PreviewRole.guardian),
        matchScreen(Uri.parse('/children/not-permitted'))!,
      ),
      isFalse,
    );
  });
  test('revoked/unlinked child preview can only reach activation', () {
    const session = PreviewSession(
      role: PreviewRole.linkedChild,
      deviceLinked: false,
    );
    expect(canOpen(session, matchScreen(Uri.parse('/child/home'))!), isFalse);
    expect(
      canOpen(session, matchScreen(Uri.parse('/child/activate'))!),
      isTrue,
    );
  });
  test(
    'rejected deep links cannot select staff or foreign child routes',
    () async {
      final router = PreviewRouter(
        session: const PreviewSession(role: PreviewRole.guardian),
      );
      await router.setNewRoutePath(Uri.parse('/children/foreign-child'));
      expect(router.selected, isNull);
      expect(router.blockedReason, isNotNull);
      await router.setNewRoutePath(Uri.parse('/ops/configuration/services'));
      expect(router.selected, isNull);
      router.dispose();
    },
  );
  test('receipt and provider acknowledgement cannot imply crew travel', () {
    const receipt = IncidentEvidence(
      delivery: DeliveryEvidence.received,
      ems: EmsEvidence.receiptOnly,
    );
    expect(receipt.message, 'Your request was received.');
    expect(
      const IncidentEvidence(crew: CrewEvidence.enRoute).message,
      'Delivery is not confirmed.',
    );
    expect(
      const IncidentEvidence(
        delivery: DeliveryEvidence.received,
        crew: CrewEvidence.accepted,
      ).message,
      isNot(contains('on the way')),
    );
    expect(
      const IncidentEvidence(
        delivery: DeliveryEvidence.received,
        crew: CrewEvidence.enRoute,
      ).message,
      contains('on the way'),
    );
    expect(
      const IncidentEvidence(
        delivery: DeliveryEvidence.received,
        crew: CrewEvidence.enRoute,
        followupReview: true,
      ).message,
      contains('separate response is not confirmed'),
    );
  });
  test(
    'requests preserve supplied ID/payload and the adapter never sends',
    () async {
      const request = HelpRequest(
        requestId: 'synthetic-request',
        childId: 'synthetic-child',
        location: null,
      );
      expect(request.toJson()['request_id'], 'synthetic-request');
      expect(request.toJson().containsKey('location'), isFalse);
      const repository = DisabledIncidentRepository(DisabledApiBoundary());
      await expectLater(
        repository.requestHelp(request),
        throwsA(isA<PreviewNetworkDisabled>()),
      );
    },
  );
}
