// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const childExperienceScreens = <ScreenSpec>[
  ScreenSpec(
    id: "C01",
    title: "Child-device activation",
    path: "/child/activate",
    purpose: "Complete guardian-initiated pairing on the child device.",
    actions:
        "Accept approved scoped pairing; explain simple child experience; guardian finishes configuration outside child context.",
    states:
        "Unlinked; challenge pending/expired; wrong child; revoked; offline.",
    phase: "M1",
    apiBoundary:
        "M: scoped credential exists; QR/challenge, secure storage and activation UX planned. Never incident-time login.",
  ),
  ScreenSpec(
    id: "C02",
    title: "Accessible child help home",
    path: "/child/home",
    purpose: "Offer the simplest individually appropriate help action.",
    actions:
        "Initiate help; access permitted comfort activity; separate supported emergency-call control; no family/staff data.",
    states:
        "Ready; active incident; offline; inactive entitlement; out-of-area; revoked/unlinked variants.",
    phase: "M1",
    apiBoundary:
        "M: help contract exists; all actual UI, individualized interaction and device permissions remain to design/build.",
  ),
  ScreenSpec(
    id: "C03",
    title: "Child request + response status",
    path: "/child/requests/:requestId",
    purpose: "Reassure using only known receipt and minimal own status.",
    actions:
        "Show sending/unconfirmed/received, acknowledged owner or actual crew progression; comfort shortcut; accidental-tap/cancellation request if suitable.",
    states:
        "Delivery unconfirmed; received; team offered/assigned/en-route; follow-up review; offline/stale; device revoked.",
    phase: "M1",
    apiBoundary:
        "M: minimal scoped status/cancellation exist; native feedback/offline behavior and child-safe copy variants planned.",
  ),
  ScreenSpec(
    id: "C04",
    title: "Comfort activity",
    path: "/child/comfort",
    purpose: "Provide only guardian-authorized comfort content.",
    actions:
        "Simple playback/pause/replay; text/visual alternative; always return to help/status easily.",
    states:
        "No content; audio unavailable; interrupted; offline content only if policy approved; audience revoked.",
    phase: "M1",
    apiBoundary:
        "M: private comfort audio access exists; secure caching and native playback policy pending. Never responder instructions.",
  ),
];
