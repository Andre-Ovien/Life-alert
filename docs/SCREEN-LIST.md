# Life alert - complete designer screen list

Draft 0.1 - October 15, 2026. **65 unique screens: 46 consumer Flutter, 19 operations (platform TBD).** No prices or scope reductions. Shared adult access is counted once. States/sheets/components are not additional screens; they still need design coverage. The state checklist is an integral companion.

Consumer: 6 shared adult access + 36 guardian/caregiver + 4 linked child. Operations: 1 staff access + 6 coordinator + 5 administration/routing + 3 responder + 4 accommodation. T02 placement authorization is coordinator-owned; Q06 routing is privileged administration despite its route group.

All screens remain in this complete baseline. M1/M2 in the detailed inventory indicate design sequencing only. There are **502 screen-state entries: 65 default layouts and 437 named variants/conditions**. These are coverage annotations, NOT 502 screens or automatically 502 artboards. The designer should identify separate layouts versus reusable variants explicitly.

## Shared adult access

| ID | Screen | Required states / variants |
| --- | --- | --- |
| A01 | Welcome + service scope | loading; offline; coverage information unavailable; returning linked child bypass |
| A02 | Adult sign in | submitting; invalid credentials; rate limited; offline; adult session expired |
| A03 | Create family account | field validation; account already exists; submitting; result unknown; offline |
| A04 | Verify contact | verification pending; invalid code; expired code; throttled; verified; offline |
| A05 | Recover access | generic recovery submitted; throttled; recovery unavailable; offline |
| A06 | Complete recovery | expired token; used token; invalid credential; success; interrupted; offline |

## Home and readiness

| ID | Screen | Required states / variants |
| --- | --- | --- |
| G01 | Family home | no children; multiple children; active incident; stale status; inactive entitlement; no entitlement data; offline |
| G02 | Readiness checklist | incomplete readiness; ready facts saved; coverage unknown; permission denied; entitlement unknown; offline |
| G03 | Updates inbox | loading; empty; refresh error; offline stale cache; access revoked |

## Household and caregiver access

| ID | Screen | Required states / variants |
| --- | --- | --- |
| H01 | Household + caregiver access | empty invites; pending invitation; accepted membership; revoked membership; authority unresolved; offline |
| H02 | Invite caregiver | invalid contact; send pending; duplicate invitation; expired invitation; send failure; offline |
| H03 | Caregiver scope + authority | scoped caregiver rights; authority verification pending; authority expired; grant revoked; contested authority; saving; offline |
| H04 | Accept invitation | wrong account; expired invitation; already used; revoked invitation; accepted; offline |

## Child care profiles

| ID | Screen | Required states / variants |
| --- | --- | --- |
| F01 | Children directory | loading; empty; multiple children; read denied; refresh error; offline stale list |
| F02 | Child overview | incomplete profile; profile update time unknown; active incident; access revoked; offline |
| F03 | Care profile editor | new child; editing existing child; field validation; unsaved changes; saving; save conflict; save failed; save outcome unknown; offline |
| F04 | Emergency contacts | empty contacts; incomplete contact; saving; unverified channel; contact authority absent; offline |
| F05 | Saved places + location | empty places; location denied; location missing; location stale; location inaccurate; saved address fallback; outside coverage; offline |

## Linked devices

| ID | Screen | Required states / variants |
| --- | --- | --- |
| D01 | Linked devices | empty; pairing pending; device revoked; device status unknown; device status stale; offline |
| D02 | Link a child device | pairing pending; expired challenge; used challenge; wrong child; pairing failed; pairing interrupted; offline |
| D03 | Device access detail | active device; lost device revoke confirmation; revoking; device revoked; revocation outcome unknown; offline |
| D04 | Child experience preferences | preferences unset; non-reader adaptation; assistive control adaptation; saving; device capability unsupported; offline |

## Care recordings

| ID | Screen | Required states / variants |
| --- | --- | --- |
| M01 | Care recordings library | loading; empty; upload pending; audio unavailable; audience access denied; offline |
| M02 | Create a recording | microphone permission denied; recording; paused; interrupted; upload progress; upload failed; upload outcome unknown; offline; invalid audio |
| M03 | Recording details + audience | loading; audience comfort only; audience responder only; audience both explicit; audience changed; playback interrupted; audio revoked; delete request pending; offline |

## Subscription and billing

| ID | Screen | Required states / variants |
| --- | --- | --- |
| B01 | Subscription + entitlement | active subscription; expired subscription; no subscription data; entitlement unknown; renewal pending; accepted incident after expiry; outside coverage with active plan; offline with active plan |
| B02 | Plan + renewal review | plans configured; pricing unavailable; no eligible plan; terms not approved; offline |
| B03 | Billing handoff + result | checkout launched; payment failed; checkout cancelled; payment pending; checkout interrupted; provider result unknown; verified entitlement success; restore access entry if applicable; restore pending or failed if applicable; offline |
| B04 | Billing history + documents | loading; empty; invoice unavailable; refund pending; access denied; offline |

## Help, incidents and temporary care updates

| ID | Screen | Required states / variants |
| --- | --- | --- |
| I01 | Parent request context | multiple children; remote parent location warning; location permission denied; location missing; location stale; location inaccurate; saved fallback; outside service area; entitlement expired; entitlement unknown; offline |
| I02 | Request delivery feedback | sending; server received; delivery unconfirmed timeout; offline not sent; duplicate tap same request; coverage rejected; entitlement rejected; revoked credential; reconnect old queued action relevance review |
| I03 | Live incident | coordinator unclaimed; coordinator claimed; no crew available; crew offered; crew declined or timed out; team accepted; team en route; team arrived; EMS provider unknown; offline stale status; subscription expires during incident; cancellation requested pending review |
| I04 | Additional help + follow-up | followup requires review; different incident location; separate emergency not independently handled; new request entitlement expired; sending; delivery unconfirmed; offline |
| I05 | Incident history | loading; empty; partial history; access revoked; offline stale history |
| I06 | Incident outcome detail | resolved assistance and handover; cancelled after review; EMS outcome uncertain; outcome detail unavailable; retention unavailable; offline |
| I07 | Temporary-care updates | capacity review; no suitable place; authority unresolved; place reserved; intake recorded; temporary care active; authorized release recorded; placement unknown; offline |
| I08 | Care authorization + recipient check | wrong person; authority missing; authority expired; contested consent; verification pending; verification failed; verified decision pending coordinator; offline |

## Settings and support

| ID | Screen | Required states / variants |
| --- | --- | --- |
| S01 | Settings + service information | loading; offline; configuration unavailable; adult session expired |
| S02 | Account + security | reauthentication; unverified contact change; change pending; session expired; offline |
| S03 | Privacy + data requests | data export request; account deletion request; correction request; request pending; legal hold review; authority denied; request failed; request fulfilled; offline |
| S04 | Notification preferences | notification permission denied; unverified channel; delivery unavailable; saving; offline |
| S05 | Support + account help | support contact unavailable; outside support hours; offline help; contact handoff failed; contact handoff unknown |

## Linked child experience

| ID | Screen | Required states / variants |
| --- | --- | --- |
| C01 | Child-device activation | unlinked; pairing pending; expired challenge; wrong child; device revoked; offline |
| C02 | Accessible child help home | non-reader help adaptation; assistive input adaptation; active incident; offline; entitlement inactive; outside coverage; revoked device; unlinked device; ordinary calling unsupported |
| C03 | Child request + response status | local sending; delivery unconfirmed; server received; coordinator owner claimed; crew offered; team assigned; team en route; followup review; accidental tap cancellation requested; offline stale status; revoked device |
| C04 | Comfort activity | no comfort content; audio unavailable; playback interrupted; offline cache not approved; audience revoked; non-audio alternative |

## Staff access - operations platform TBD

| ID | Screen | Required states / variants |
| --- | --- | --- |
| O01 | Staff access + role landing | no authorized role; region mismatch; MFA pending; session expired; offline |

## Coordinator/routing operations - platform TBD

| ID | Screen | Required states / variants |
| --- | --- | --- |
| Q01 | Regional incident queue | loading; empty; unclaimed; no crew; overdue; review flag; offline stale feed |
| Q02 | Coordinator incident workspace | unowned; owned by another; takeover reason; missing location; stale location; followup review; provider unknown; offline |
| Q03 | Crew review + offers | no available crew; offer pending; declined with reason; offer timed out; team accepted; availability changed; offline |
| Q04 | EMS handoff + evidence | handoff pending; provider receipt only; provider unknown; contact confirmed; dispatch confirmed; arrival confirmed; no dispatch; closed with evidence; offline |
| Q05 | Outcome + response reconciliation | crew unreconciled; EMS unknown; placement unreconciled; authority mismatch; incomplete outcome; cancellation review; resolved after verified disposition; offline |
| Q06 | Unrouted incident review | loading; empty; missing location; stale location; ambiguous region; no eligible region; responsibility verified; offline |

## Responder operations - platform TBD

| ID | Screen | Required states / variants |
| --- | --- | --- |
| R01 | Crew offers | empty; offer pending; expired offer; declined with reason; accepted; team already assigned elsewhere; offline |
| R02 | Assigned response + care | accepted; en route; arrived; location update unknown; care audio unavailable; offline; assignment access ended |
| R03 | Crew care handover | recipient unverified; handover pending; incomplete assistance record; submitted to coordinator; offline |

## Temporary-care operations - platform TBD

| ID | Screen | Required states / variants |
| --- | --- | --- |
| T01 | Facility + places overview | loading; empty; no suitable place; capacity full; stale capacity; staff unavailable; offline |
| T02 | Placement suitability + authority | no capacity; authority unresolved; reservation conflict; reserved; offline |
| T03 | Staff assignment + intake | staff unassigned; transport arrival pending; intake discrepancy; authority conflict; intake complete; offline |
| T04 | Active care + staff handover | active care; shift change; care issue escalation; handover pending; access expired; offline |
| T05 | Verified release + handover | wrong recipient; identity unverified; authority missing; contested release; approved release; released; offline |

## Administration - platform TBD

| ID | Screen | Required states / variants |
| --- | --- | --- |
| N01 | Service regions + provider configuration | disabled region; unapproved configuration; save failure; provider unavailable; simulation mode; offline |
| N02 | Staff roles + crews | staff coverage missing; qualification missing; availability stale; staff access revoked; saving; offline |
| N03 | Commercial + entitlement administration | billing unknown; active entitlement; expired entitlement; reconciliation pending; invalid interval; offline |
| N04 | Privacy + audit oversight | audit unavailable; access denied; retention legal hold; data request pending; offline |

## Required non-screen deliverables

Reusable accessible help/status/location/audio components; contact/address forms; cancellation REQUEST, revoke-device, unsaved-change, consent/identity, ordinary-call handoff, recording deletion request and privacy/account data-request sheets. Include loading, empty, error/retry, offline/stale, session expiry, revoked access, permission denied and unknown-result patterns where mapped. Include Android/iOS adaptation notes, accessible non-reader alternatives and clickable core journeys. Native OS dialer/payment/permission dialogs are platform handoffs, not invented custom app screens.

Billing B03 explicitly includes failed, cancelled, pending, interrupted, provider-unknown and verified-success results. Restore/reconcile access is conditional on the billing approach selected later. No pricing/vendor is assumed. The child never signs in or seeks parent approval at incident time. Real payment, production identity and live providers remain pending integrations.

Actions, entry/exit, permissions, accessibility, route IDs, sequencing and PRD references are specified in [DESIGNER-HANDOFF.md](DESIGNER-HANDOFF.md). Every state maps to a screen in [SCREEN-STATE-CHECKLIST.csv](SCREEN-STATE-CHECKLIST.csv). Ask the designer to acknowledge included IDs/states and list exclusions. New client workflows may change the labeled baseline later.
