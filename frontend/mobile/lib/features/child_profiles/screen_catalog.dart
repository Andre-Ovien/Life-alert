// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const childProfilesScreens = <ScreenSpec>[
  ScreenSpec(
    id: "F01",
    title: "Children directory",
    path: "/children",
    purpose: "Select a child within authorized household scope.",
    actions:
        "Open child; add child if guardian; show active incident/readiness summary.",
    states: "Empty; loading; read denied; failed refresh; offline/stale.",
    phase: "M1",
    apiBoundary:
        "F: guardian child list/create/read/update exists; scoped invite rights planned.",
  ),
  ScreenSpec(
    id: "F02",
    title: "Child overview",
    path: "/children/:childId",
    purpose: "Summarize the individual care plan and readiness.",
    actions:
        "Review communication/support/calming summary; open profile, contacts, places, devices, recordings and help.",
    states:
        "Incomplete profile; latest-update uncertainty; active incident; access revoked; offline.",
    phase: "M1",
    apiBoundary:
        "M: latest profile exists; version snapshots, readiness summary and detailed update history planned.",
  ),
  ScreenSpec(
    id: "F03",
    title: "Care profile editor",
    path: "/children/:childId/edit",
    purpose: "Create/edit individual support and communication information.",
    actions:
        "Record strengths, communication, support needs, calming preferences and relevant instructions; review before saving.",
    states:
        "Validation; unsaved; saving; conflict; failed/unknown save; offline.",
    phase: "M1",
    apiBoundary:
        "M: core text fields/update exist; extra fields, version/concurrency policy need design/API agreement.",
  ),
  ScreenSpec(
    id: "F04",
    title: "Emergency contacts",
    path: "/children/:childId/contacts",
    purpose:
        "Keep relevant contacts visible without granting collection authority.",
    actions:
        "View contact order/details; add/edit via contact sheet; distinguish role and authority status.",
    states:
        "Empty; incomplete contact; saving; delivery channel unverified; offline.",
    phase: "M1",
    apiBoundary:
        "M: list/create/read exists; edit/order/verification and authority workflow planned.",
  ),
  ScreenSpec(
    id: "F05",
    title: "Saved places + location",
    path: "/children/:childId/places",
    purpose: "Manage labeled address fallbacks and location expectations.",
    actions:
        "Review/add saved address; name place; show fallback status and permission guidance.",
    states:
        "No address; stale/denied location; inaccurate fix; fallback; unsupported area; offline.",
    phase: "M1",
    apiBoundary:
        "M: one saved address/core location exists; multi-place CRUD/maps/geocoding planned.",
  ),
];
