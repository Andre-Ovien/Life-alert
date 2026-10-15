// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const householdScreens = <ScreenSpec>[
  ScreenSpec(
    id: "H01",
    title: "Household + caregiver access",
    path: "/household",
    purpose: "Show household membership and authorized scope.",
    actions:
        "Review members and pending invites; open person scope; invite if guardian.",
    states:
        "No invites; pending; accepted; revoked; authority unresolved; offline.",
    phase: "M2",
    apiBoundary:
        "M: guardian membership exists; invitations and scoped caregiver grants planned.",
  ),
  ScreenSpec(
    id: "H02",
    title: "Invite caregiver",
    path: "/household/invite",
    purpose: "Propose explicit limited caregiver access.",
    actions:
        "Choose person/contact, child scope and allowed actions; review invitation before sending.",
    states:
        "Invalid contact; pending send; duplicate; expiry; failure; offline.",
    phase: "M2",
    apiBoundary:
        "P: invite delivery/grants unsupported; no assumed consent or guardianship.",
  ),
  ScreenSpec(
    id: "H03",
    title: "Caregiver scope + authority",
    path: "/household/members/:memberId",
    purpose: "Review permissions separately from legal care/release authority.",
    actions:
        "Inspect child/action grants; request verified authority review; revoke access using a reviewed flow.",
    states:
        "Pending verification; valid/expired/revoked grants; contested authority; saving; offline.",
    phase: "M2",
    apiBoundary:
        "P: current foundation has guardian relations only; authority/grant lifecycle planned.",
  ),
  ScreenSpec(
    id: "H04",
    title: "Accept invitation",
    path: "/household/invitations/:inviteId",
    purpose: "Accept only the offered scope after adult authentication.",
    actions:
        "Review inviter, children and allowed actions; accept/decline; do not broaden grants.",
    states: "Expired; already used; revoked; wrong account; accepted; offline.",
    phase: "M2",
    apiBoundary: "P: invitation and scoped caregiver endpoints planned.",
  ),
];
