// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const incidentsScreens = <ScreenSpec>[
  ScreenSpec(
    id: "I01",
    title: "Parent request context",
    path: "/help/new",
    purpose: "Identify child and incident location with minimal friction.",
    actions:
        "Choose authorized child; review child/incident location and labeled fallback; initiate paid organizational help or separate ordinary calling.",
    states:
        "Location denied/missing/stale/inaccurate; remote parent; coverage unsupported; entitlement unknown/expired; offline.",
    phase: "M1",
    apiBoundary:
        "M: help/location/entitlement contract exists; native permission/routing map UX planned. Do not default to remote parent location.",
  ),
  ScreenSpec(
    id: "I02",
    title: "Request delivery feedback",
    path: "/help/requests/:requestId",
    purpose:
        "Distinguish local tap, pending transmission and durable server receipt.",
    actions:
        "Show sending/unconfirmed/received; retry identical request safely; open incident; separate ordinary calling.",
    states:
        "Sending; server received; timeout unknown; offline; invalid/revoked access; coverage/entitlement error.",
    phase: "M1",
    apiBoundary:
        "M: atomic acceptance/replay exists; device persistence/offline queue/relevance review planned.",
  ),
  ScreenSpec(
    id: "I03",
    title: "Live incident",
    path: "/incidents/:incidentId/live",
    purpose: "Show known response facts without a false promise.",
    actions:
        "View coordinator/crew/EMS/placement milestones and last update; request cancellation; add follow-up; inspect care updates.",
    states:
        "Received; owner unclaimed/claimed; offered/accepted/en-route; provider unknown; stale/offline; expiry during accepted care.",
    phase: "M1",
    apiBoundary:
        "M: scoped statuses and cancellation request exist; push/live refresh, outcome detail and richer caregiver updates planned.",
  ),
  ScreenSpec(
    id: "I04",
    title: "Additional help + follow-up",
    path: "/incidents/:incidentId/follow-up",
    purpose:
        "Provide new emergency information without pretending separate dispatch.",
    actions:
        "Describe or route new context through approved future input; preserve original request result; explicitly request review.",
    states:
        "Review pending; entitlement expired for new paid request; sending/unconfirmed; different location; offline.",
    phase: "M1",
    apiBoundary:
        "M: new request ID records location/review flag for one open incident. Free-text family follow-up and independent simultaneous incidents not supported yet.",
  ),
  ScreenSpec(
    id: "I05",
    title: "Incident history",
    path: "/incidents/history",
    purpose: "Find permitted past and current incidents.",
    actions:
        "List/filter own child incidents; open live or completed record; show missing history honestly.",
    states: "Empty; loading; partial history; access revoked; offline/stale.",
    phase: "M1",
    apiBoundary:
        "M: scoped incident list exists; advanced filtering/archive and retention policy planned.",
  ),
  ScreenSpec(
    id: "I06",
    title: "Incident outcome detail",
    path: "/incidents/:incidentId",
    purpose: "Explain recorded assistance and handover after response.",
    actions:
        "Review known timeline, outcome and approved follow-up; open placement history; contact support.",
    states:
        "Resolved; cancelled after review; incomplete/uncertain evidence; retention unavailable; offline.",
    phase: "M1",
    apiBoundary:
        "M: outcome stored; family-readable outcome/timeline/handover API incomplete. Do not infer external cancellation.",
  ),
  ScreenSpec(
    id: "I07",
    title: "Temporary-care updates",
    path: "/incidents/:incidentId/care",
    purpose: "Show whether placement is considered, confirmed or active.",
    actions:
        "View suitability/capacity review, authorized location/status and handover updates; respond to permitted authorization tasks.",
    states:
        "No place; authority unresolved; reserved; intake; active care; released; unknown/offline.",
    phase: "M1",
    apiBoundary:
        "M: placement states exist; detailed parent-facing placement/status/staff/transport APIs planned.",
  ),
  ScreenSpec(
    id: "I08",
    title: "Care authorization + recipient check",
    path: "/incidents/:incidentId/care/authorization",
    purpose: "Support protected consent/authorized-recipient verification.",
    actions:
        "Review placement/release request, authority basis and permitted identity steps; confirm only within verified authority or ask coordinator.",
    states:
        "Wrong person; authority missing/expired; contested consent; verification pending/failed; offline.",
    phase: "M1",
    apiBoundary:
        "P: structured consent/identity verification not implemented; emergency-contact status is insufficient.",
  ),
];
