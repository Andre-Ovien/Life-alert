// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const linkedDevicesScreens = <ScreenSpec>[
  ScreenSpec(
    id: "D01",
    title: "Linked devices",
    path: "/children/:childId/devices",
    purpose: "Review device access for this child.",
    actions:
        "List links, limited status and revoked devices; start secure linking; open device detail.",
    states:
        "No devices; linking pending; revoked; status unknown/stale; offline.",
    phase: "M1",
    apiBoundary:
        "M: device list/create/revoke exists; live heartbeat/capabilities and pairing planned.",
  ),
  ScreenSpec(
    id: "D02",
    title: "Link a child device",
    path: "/children/:childId/devices/link",
    purpose: "Establish scoped child access before an incident.",
    actions:
        "Guide approved secure pairing; explain child scope; complete setup on target device.",
    states:
        "Pairing pending; expired/used challenge; wrong child; interrupted; offline.",
    phase: "M1",
    apiBoundary:
        "M: one-time returned credential exists; secure native pairing UX/protocol still planned. Never expose raw permanent tokens in designs.",
  ),
  ScreenSpec(
    id: "D03",
    title: "Device access detail",
    path: "/children/:childId/devices/:deviceId",
    purpose: "Manage one linked device and recover lost access.",
    actions:
        "View linked child and access status; revoke with explicit impact sheet; replace link.",
    states: "Active; revoked; revoking; failed/unknown request; offline.",
    phase: "M1",
    apiBoundary:
        "M: revocation exists; richer status and replacement/rotation policy planned.",
  ),
  ScreenSpec(
    id: "D04",
    title: "Child experience preferences",
    path: "/children/:childId/experience",
    purpose:
        "Prepare individual child interaction choices behind adult access.",
    actions:
        "Select accessible feedback, comfort content and interaction adaptations validated with the child.",
    states:
        "Unset; saving; incompatible device feature; offline; permission denied.",
    phase: "M1",
    apiBoundary:
        "P: child UI preferences/capabilities API planned; no diagnosis-based presets or secret bypass gestures.",
  ),
];
