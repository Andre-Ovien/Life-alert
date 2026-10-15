// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const settingsSupportScreens = <ScreenSpec>[
  ScreenSpec(
    id: "S01",
    title: "Settings + service information",
    path: "/settings",
    purpose: "Find adult account, privacy, notification and support controls.",
    actions:
        "Open account/security/privacy/preferences/support; view service terms/version; sign out adults.",
    states: "Loading settings; offline; update unavailable; session expired.",
    phase: "M1",
    apiBoundary:
        "M: adult logout exists; aggregated preferences/legal content/configuration planned.",
  ),
  ScreenSpec(
    id: "S02",
    title: "Account + security",
    path: "/settings/account",
    purpose: "Manage adult identity and access safely.",
    actions:
        "Review contact/security sessions; request contact/password change through approved flow; view guardian verification status.",
    states:
        "Reauthentication; unverified change; pending; expired session; offline.",
    phase: "M2",
    apiBoundary:
        "P: account edits, production sessions/MFA/verification planned; no sensitive credential changes implemented by this document.",
  ),
  ScreenSpec(
    id: "S03",
    title: "Privacy + data requests",
    path: "/settings/privacy",
    purpose: "Explain access/retention and request reviewed data actions.",
    actions:
        "Read purpose/retention notices; request export/correction/deletion or account closure; view request status.",
    states:
        "Pending request; legal hold/review; denied authority; failed; fulfilled; offline.",
    phase: "M2",
    apiBoundary:
        "P: no deletion/export endpoints; retention/consent/legal review pending. No promise of immediate erasure.",
  ),
  ScreenSpec(
    id: "S04",
    title: "Notification preferences",
    path: "/settings/notifications",
    purpose: "Control approved channels and understand delivery limitations.",
    actions:
        "Review notification permission/channel verification and preference scope; open OS settings only with intent.",
    states:
        "Permission denied; channel unverified; delivery unavailable; saving/offline.",
    phase: "M1",
    apiBoundary:
        "P: live channels/preferences not implemented; critical alert rules and user controls require client/platform validation.",
  ),
  ScreenSpec(
    id: "S05",
    title: "Support + account help",
    path: "/support",
    purpose: "Provide service/account guidance and approved contact options.",
    actions:
        "Read help; contact approved support; route billing/account issues; expose separate ordinary emergency calling when supported.",
    states:
        "Support details unavailable; outside support hours; offline; handoff failed/unknown.",
    phase: "M1",
    apiBoundary:
        "P: support channels/hours not supplied; never invent a 24/7 staffed channel or imply support contacts EMS.",
  ),
];
