// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const subscriptionsScreens = <ScreenSpec>[
  ScreenSpec(
    id: "B01",
    title: "Subscription + entitlement",
    path: "/subscription",
    purpose: "Show paid eligibility separately from coverage/connectivity.",
    actions:
        "View status/effective dates and existing incident continuity; renew or manage through approved billing flow.",
    states:
        "Active; expired; inactive; unknown; renewal pending; offline/out-of-area independent.",
    phase: "M1",
    apiBoundary:
        "M: local ledger/incident evidence exist; family entitlement read API and real billing planned.",
  ),
  ScreenSpec(
    id: "B02",
    title: "Plan + renewal review",
    path: "/subscription/plans",
    purpose: "Explain client-approved paid services before purchase/renewal.",
    actions:
        "Review configured terms, service limits and pricing when supplied; select plan; continue.",
    states: "Pricing unavailable; no eligible plan; terms pending; offline.",
    phase: "M1",
    apiBoundary:
        "P: no pricing, vendor, plan catalogue or payment eligibility decided; placeholders are explicit.",
  ),
  ScreenSpec(
    id: "B03",
    title: "Billing handoff + result",
    path: "/subscription/billing",
    purpose:
        "Manage purchase/renewal through an approved future billing boundary.",
    actions:
        "Launch approved platform/provider payment flow; reconcile success/pending/failure; manage cancellation/refund request per policy.",
    states:
        "Cancelled checkout; failed; pending; verified success; duplicate return; unknown/offline.",
    phase: "M1",
    apiBoundary:
        "P: no real processing. Payment acknowledgement alone does not activate entitlement; platform/payment approach pending.",
  ),
  ScreenSpec(
    id: "B04",
    title: "Billing history + documents",
    path: "/subscription/history",
    purpose:
        "Review authorized household billing records and support references.",
    actions:
        "List verified transactions/documents; open invoice; request billing support.",
    states:
        "Empty; unavailable invoice; pending/refund state; access denied; offline.",
    phase: "M2",
    apiBoundary:
        "P: billing records/export/refund API planned; do not design fabricated prices or invoices.",
  ),
];
