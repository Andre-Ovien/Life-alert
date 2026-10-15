// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const homeReadinessScreens = <ScreenSpec>[
  ScreenSpec(
    id: "G01",
    title: "Family home",
    path: "/home",
    purpose: "Orient the adult and foreground active care.",
    actions:
        "Select authorized child; open active incident; request help; view readiness/subscription indicators.",
    states:
        "No child; active incident; unknown/stale status; inactive entitlement; offline.",
    phase: "M1",
    apiBoundary:
        "M: core records exist; aggregate dashboard/push entry planned.",
  ),
  ScreenSpec(
    id: "G02",
    title: "Readiness checklist",
    path: "/readiness",
    purpose: "Explain separately what is ready and missing.",
    actions:
        "Review profile, contacts, device, subscription and coverage; complete one item at a time.",
    states:
        "Incomplete; saved; unavailable coverage; denied permissions; offline; entitlement unknown.",
    phase: "M1",
    apiBoundary:
        "M: source records exist; readiness aggregation and verified coverage-hours model planned.",
  ),
  ScreenSpec(
    id: "G03",
    title: "Updates inbox",
    path: "/updates",
    purpose:
        "Collect permitted family updates without treating delivery as ownership.",
    actions:
        "Open incident/placement update; mark read; review delivery/acknowledgement context.",
    states:
        "Empty; loading; failed refresh; stale/offline cache; permission lost.",
    phase: "M2",
    apiBoundary:
        "P: inbox, real delivery and push not implemented; receipt simulation is not a live inbox.",
  ),
];
