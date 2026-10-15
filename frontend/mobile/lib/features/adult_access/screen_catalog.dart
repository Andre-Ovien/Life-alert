// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const adultAccessScreens = <ScreenSpec>[
  ScreenSpec(
    id: "A01",
    title: "Welcome + service scope",
    path: "/welcome",
    purpose: "Explain service and begin adult access.",
    actions:
        "Read service boundaries; sign in; create family; access supported ordinary emergency calling.",
    states:
        "Loading configuration; unavailable coverage info; offline; returning device mode.",
    phase: "M1",
    apiBoundary: "P: production onboarding; service claims need client review.",
  ),
  ScreenSpec(
    id: "A02",
    title: "Adult sign in",
    path: "/access/sign-in",
    purpose: "Authenticate guardian or invited caregiver.",
    actions:
        "Sign in using approved future identity method; recover access; return to allowed deep link.",
    states:
        "Submitting; invalid credentials; locked/rate-limited; offline; session expired.",
    phase: "M1",
    apiBoundary:
        "M: local session/CSRF exists; native auth, MFA and token renewal not final.",
  ),
  ScreenSpec(
    id: "A03",
    title: "Create family account",
    path: "/access/register",
    purpose: "Create an adult account and household.",
    actions:
        "Enter minimum account/household fields; review required notices; submit registration.",
    states:
        "Validation; duplicate account; submitting; failed/unknown result; offline.",
    phase: "M1",
    apiBoundary:
        "M: local username registration exists; production consent/contact verification planned.",
  ),
  ScreenSpec(
    id: "A04",
    title: "Verify contact",
    path: "/access/verify",
    purpose:
        "Verify approved account contact without asserting legal authority.",
    actions: "Enter link/code; resend under approved policy; correct contact.",
    states: "Pending; invalid/expired code; throttled; verified; offline.",
    phase: "M1",
    apiBoundary:
        "P: channel, verification provider and expiry rules undecided.",
  ),
  ScreenSpec(
    id: "A05",
    title: "Recover access",
    path: "/access/recover",
    purpose: "Start secure adult account recovery.",
    actions:
        "Provide approved account identifier; request recovery; receive non-enumerating feedback.",
    states:
        "Generic submitted result; offline; throttled; recovery unavailable.",
    phase: "M1",
    apiBoundary: "P: recovery service not implemented.",
  ),
  ScreenSpec(
    id: "A06",
    title: "Complete recovery",
    path: "/access/recover/complete",
    purpose: "Finish verified recovery and return to adult access.",
    actions:
        "Use verified recovery token; set new credential through approved identity flow; review session impact.",
    states:
        "Expired/used token; invalid credential; success; interrupted; offline.",
    phase: "M1",
    apiBoundary:
        "P: identity provider and credential/session rules pending; never child help gate.",
  ),
];
