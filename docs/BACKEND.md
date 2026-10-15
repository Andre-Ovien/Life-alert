# Backend and API guide

Updated October 15, 2026. The backend implements the controllable PRD workflows using local simulations and protected manual evidence. It does not operate a live emergency, payment, messaging or care service. The [completion matrix](BACKEND-COMPLETION.md) maps requirements to evidence and external launch decisions. The reviewed source of product intent remains [PRD.md](PRD.md).

The baseline was published at `bebe4a97be12300482514ddd6fad3e35ebdb9ea4`. The subsequent backend implementation and documentation are tracked on [`codex/response-workflow-reliability`](https://github.com/Andre-Ovien/Life-alert/tree/codex/response-workflow-reliability) for GitHub review. The Flutter foundation exists separately under `frontend/mobile`; these backend changes do not alter the mobile UI or designer PDF snapshots.

## Reproduce and verify

Use the root README for installation. Exact dependencies are pinned in `requirements.txt`: Django/DRF, PostgreSQL driver, PyOTP, cryptography and drf-spectacular with their dependencies. Settings read shell environment variables directly; `.env.example` is reference material, not automatically loaded. No default account, child data, entitlement or active region is seeded.

From the repository root:

```sh
make migrate
make check
make test
make test-postgres
make schema
```

SQLite supports single-process exploration. PostgreSQL is required for concurrent workflows. `make test-postgres` uses the installed PostgreSQL tools to create an isolated, socket-only temporary cluster, runs all tests, then stops and removes it. It does not use an existing application database. Tests use synthetic people, locations and temporary media.

`make schema` validates and regenerates [openapi.yaml](openapi.yaml), failing on schema warnings. Authenticated clients can also retrieve `/api/v1/schema/`. The contract describes requests, response envelopes and role-dependent projections; it does not relax authorization. The server validates operational conditions beyond field shapes, such as ownership, current authority, capacity and review state. HTTP 400/401/403/404/429 responses can contain field-specific validation details.

## Authentication and purpose boundaries

Registration uses `GET /api/v1/session/` for a CSRF cookie/token, then `POST /api/v1/register/` with `username`, `password` and `household_name`. Registration creates an adult guardian household and grants no paid service or legal authority. Cookie sign-in uses `POST /api/v1/session/`; send cookies and `X-CSRFToken` on subsequent mutations. `DELETE` logs out.

Native adult clients use `POST /api/v1/mobile/token/` with username/password and `Authorization: Bearer <access_token>`. Access and refresh credentials are returned once and stored only as hashes. `mobile/refresh/` rotates both credentials; reuse of a consumed refresh credential revokes its session, with revocation committed before returning an error. `mobile/logout/` revokes the current bearer session or all adult sessions with `all_sessions=true`. Password recovery also revokes adult bearer sessions. These actions do not revoke a linked child device.

Contact and recovery endpoints are `mobile/contact-challenges/`, `mobile/recovery/` and `mobile/challenges/{contact|recovery}/complete/`. Challenges are hashed, expiring and single-use. Public recovery responses do not enumerate eligible accounts. Delivery is simulated: public responses never expose challenge secrets and no email/SMS is sent. A reviewed real delivery adapter is required before production contact verification/recovery can function. Contact proof grants no guardianship, caregiver permission or release authority.

`mobile/mfa/` returns enrollment status. `mobile/mfa/{enroll|confirm|verify|disable}/` manages TOTP. Enrollment and disable require password reauthentication; disable also requires a current factor. Enrollment secrets are returned once and encrypted in the database with Fernet using a key derived from the Django secret. Confirmation returns eight recovery codes once; only their hashes persist. TOTP counters and recovery codes cannot be replayed. Verification belongs to the current bearer or CSRF-protected cookie session, expires independently of access-token rotation, and must follow current enrollment. Password recovery does not remove MFA. Key rotation requires a reviewed migration/re-enrollment procedure; changing the Django secret without one makes existing TOTP secrets unreadable.

With `DEBUG=0`, MFA is enforced for configuration admins, staff, coordinators, team members, care staff and privacy/audit reviewers. Ordinary guardians and linked child devices do not acquire an incident-time MFA or parent-login dependency. Local development leaves staff enforcement off; tests explicitly exercise enforcement on.

A guardian or appropriately delegated caregiver creates a device or starts `device-pairing/`. Pairing tokens are one-use, expiring and manually shared; `device-pairing/consume/` exchanges one for a child credential. Child requests use `Authorization: Device <credential>`. Rotation replaces and revokes the old credential atomically; explicit revocation and optional expiry apply during both authentication and acceptance. Mobile clients must supply secure native credential storage.

Configuration superusers can administer operating records but have no automatic child/incident browsing entitlement. Coordinators are regional; crews need a current accepted assignment to read care/location; facility staff need a reviewed, active, on-duty facility membership and a current placement assignment. Ended assignments and placements remove operational access. Caregiver rights are explicit, expiring and revocable. Emergency contacts, invitations and contact verification never imply legal authority.

## API groups

All routes below are relative to `/api/v1/`. UUIDs are opaque identifiers, not security controls. Lists normally paginate under `count`, `next`, `previous`, `results`; the schema records bounded `results`-only operational projections. There are no domain-record DELETE endpoints.

| Group | Main routes and actions | Behavior |
| --- | --- | --- |
| Family | `households/`, `children/`, `contacts/`, `places/` | Family isolation; individual communication/support/calming information and labeled saved locations |
| Care versions | `children/{id}/versions/`, `readiness/` | Immutable care snapshots; updates require `expected_version`; readiness reports facts without guaranteeing eligibility |
| Caregivers | `caregiver-invitations/`, `consume/`, `{id}/revoke/`; `caregiver-grants/`, `{id}/revoke/` | Recipient-bound invitation, explicit rights and immediate revocation |
| Authority | `authorities/`, `{id}/review/` | Pending evidence and operator-recorded external verification with purpose, subject and validity |
| Devices | `devices/`, `{id}/revoke/`, `{id}/rotate/`; `device-pairing/`, `{id}/revoke/`, `consume/` | Hashed credentials, one-use pairing and replacement |
| Media | `media/`, `{id}/upload/`, `{id}/audio/` | Audience-specific metadata, private authenticated streaming and text alternatives |
| Entitlement | `households/{id}/entitlement/`; `configuration/entitlements/`, `configuration/billing-events/` | Factual eligibility; sandbox/manual updates only; normalized event revisions, replay and stale-event handling |
| Help | `incidents/help/`, `incidents/`, `incidents/{id}/` | Durable acceptance, idempotency, minimal child response and scoped adult state |
| Coordination | Incident actions `claim-ownership`, `progress`, `followups`, `acknowledge-notification`, `escalations`, `escalation-transition` | Accountable owner, recorded actions/next steps, durable unowned/failed/uncertain tasks |
| Crew | Incident `offer-team`, `response-plan`; `my-offers/`, `{id}/transition/` | Reviewed candidates, real acceptance before assignment, decline/timeout fallback and minimal pre-acceptance disclosure |
| Location | Incident `location-updates`, `review-location`, `region-handover`; `region-handovers/`, `{id}/accept/`, `{id}/decision/` | Idempotent observations, explicit review and receiving-owner acceptance; decline/cancel retains current responsibility |
| EMS | Incident `ems-evidence`, `ems-events` | Separate provider receipt/contact/dispatch/arrival evidence; immutable idempotent manual event ledger |
| Care | Incident `reserve-placement`, `placement-transition`, `care-placements`; `placements/`, `{id}/assign-staff/`, `accept-handover/`, `handover-decision/`, `handovers/`, `events/`, `transition/` | Capacity, current reviewed authority, staff acceptance, intake/shift/release and thin family updates |
| Closure | Incident `request-cancellation`, `transition` | Cancellation request does not terminate response; owner disposition reconciles active branches and tasks |
| Privacy | `privacy-requests/`, `{id}/review/`, `export/`, `correct/`, `media-hold/` | Requester scope, explicit reviewer permission, retained decision history and legal-hold hooks |
| Audit | `audit-events/?object_id={uuid}` | Explicit security-review permission and exact-object scope; structural facts only; reads are audited |
| Configuration | `configuration/regions`, `teams`, `facilities`, `care-places`, `facility-staff`, `coordinators`, `response-policies`, `retention-policies`, `unrouted` | Audited admin controls; disabled/unconfigured policies do not invent approved operations |

## Acceptance, location and subscription

Help requests use `child`, a client-preserved UUID `request_id`, and optional `location` containing `latitude`, `longitude`, `accuracy_meters` and ISO `captured_at`. Preserve the original payload across transport retries. All supplied location fields must be valid, finite values. Missing location can enter manual routing review; saved addresses remain explicitly labeled fallback. Fresh coordinates outside enabled pilot rectangles are rejected with a coverage result. Overlapping, stale or imprecise location requires review; it is never relabeled as a live fix.

Acceptance and every entitlement writer lock the household first. Credentials are rechecked under that boundary. The incident, request mapping, care snapshot, independent notification jobs, EMS work record and audit commit before the server reports receipt. Receipt means persistence, not an accepted crew, contact with EMS or dispatch.

An identical authorized request replay returns its original incident even after subscription expiry. New paid request IDs require current entitlement. One open incident per child is enforced by a database constraint. Another request ID during an open incident records its own location/timestamp, sets review required and returns `followup_requires_review`. Separate simultaneous emergencies require explicit coordinator reconciliation; no extra dispatch is fabricated. Location-observation/review and regional-handover APIs support this reconciliation without treating an observation as a new paid request.

Accepted care continues after entitlement expiry. `CONTINUE_ACCEPTED_INCIDENTS=0` only changes the reported policy-review flag; it cannot stop accepted care. Ordinary native emergency calling remains separate from the paid backend and needs actual device capabilities.

## Workers, truthful state and escalation

`make work` runs one local simulation pass. `process_work --max-jobs 100` bounds notification attempts. Notification jobs have durable attempts, bounded retries/backoff, claim leases and fencing tokens. Provider simulation occurs outside the claim/finalization transactions. A simulated receipt lets an interrupted worker reconcile without resending. Unknown outcomes block for review; exceptions retain controlled codes rather than private raw messages. Closed incidents and obsolete offers/handovers cancel unsent jobs. No scheduler, live provider or real outbound recipient is enabled.

Parent, organization and EMS branches operate independently. Parent acknowledgement never gates crew or EMS work. Notification receipt/acknowledgement, coordinator ownership, crew offer/acceptance/en-route/arrival, EMS contact/dispatch/arrival and placement states remain separate. Public messages reflect recorded facts and do not promise an ETA. The proposed 5–10 minute target remains a client decision, not a system guarantee.

Approved response automation requires both an enabled regional response policy with named primary/backup and explicit timing/reference, and an owner-reviewed incident plan with ordered suitable candidate teams. Care/location changes invalidate the relevant plan review. Availability, duty, membership and prior attempts are checked again at offer time. A sent offer is not an assignment; acceptance is atomic. Declines/timeouts can offer the next reviewed candidate. Exhaustion and missing ownership create durable escalation and simulated backup alerts. Human acknowledgement alone does not claim incident ownership or resolve a task.

The current coordinator owner actively arranges the response and records `action_taken` and `next_steps`. Takeover requires a reason. Regional transfer requires a named eligible receiver's acceptance; decline/cancellation preserves the current owner. Existing accepted crews are retained through regional review instead of duplicated. Reconcile any pending handover when responsibility changes; incident closure cancels unaccepted regional handovers.

EMS simulation produces at most provider acknowledgement or uncertainty. Manual evidence events require explicit state/evidence and optionally an idempotent event UUID/observed timestamp. Replay cannot regress a later state. A provider receipt is never EMS contact/dispatch. Unknown EMS outcomes also create one durable reconciliation task. Human reconciliation is required before any potentially duplicating external action and before that task can be resolved.

## Temporary care and closure

A reservation requires enabled reviewed facility/place capacity, operator suitability confirmation and a current verified placement-authority record. Operator assertions reference real external verification; the software does not establish legal authority. Facility and place locks prevent double allocation. No capacity creates a persistent task, not a booking. A configured reservation expiry cancels only pre-intake capacity and escalates; it never automatically discharges a child already in care.

Named, approved on-duty receiving staff get the relevant protected care subset and must accept responsibility before intake. Intake requires transport/intake references and records intake time and belongings. Shift changes retain the current owner until the named recipient accepts. Decline/cancel records the decision, removes unaccepted recipient access and permits a replacement handover. Care event UUIDs are idempotent; supported events are support, observation and handover notes, without inventing clinical treatment scope.

Release requires the matching current reviewed release-recipient authority, explicit handover reference and no pending shift handover. Release records the recipient, evidence and time, then removes facility-staff access. A parent-facing placement projection excludes belongings, private authority evidence and staff details.

Cancellation requests only request review. Closure requires authorized coordinator ownership, explicit disposition, no unresolved escalations and reconciled crew/EMS/placement branches. Resolution requires a narrative plus structured `assistance`, `handover`, `ems_disposition` and `followup` details. No placement is required when the actual assistance/disposition is documented. Software cannot establish the truth of real-world handover assertions.

## Media and privacy lifecycle

Audio is private PCM WAV, at most 5 MiB and 180 seconds; frame completeness, duration and format are validated. Storage paths/URLs are not exposed. All API responses use `private, no-store`. Upload replacement retains the previous private blob instead of silently orphaning/deleting it. Only applicable child comfort or operational instruction audiences can read it.

Privacy requests support reviewed export, versioned child correction, media deletion and adult account closure. A dedicated Django permission controls review. Approval, holds and hold removal retain decision history. Export is requester-only, purpose-scoped application data; audio, credentials, staff private identity and provider raw records are excluded and labeled. It is not a claim of complete statutory disclosure.

Unknown retention policy or legal hold prevents media purging. Reviewed media deletion first archives access, then schedules physical deletion after applicable recorded bounds. `purge_reviewed_media` is dry-run by default; `--apply` processes only reviewed, due local FileSystemStorage files and retired blobs, with current holds/policy rechecked under locks. Tests purge temporary synthetic files only. No cloud/backups/cache deletion adapter exists without a selected storage/retention policy.

Account closure holds while the adult has active family care, coordinator ownership, crew/placement duties or acknowledged escalation responsibility, or disabling the last active guardian would orphan a household with children. Otherwise it deactivates the adult and revokes adult bearer sessions; it does not hard-delete evidence or revoke child access. Closure serializes against new acceptance and staff responsibility acquisition; an in-flight staff mutation rechecks the adult account under the same user lock. Deactivation is not a claim of erasing retained records, exports, backups or native cached media.

## Health and deployment boundary

`/health/` reports process liveness and simulated-provider mode. `/health/ready/` returns 200 only when the database is reachable, migrations are current and a configured production cache is usable; failures return a generic 503 without connection details. `live_service_ready` remains false. Infrastructure readiness does not assert staffed, legally approved service readiness.

`DEBUG=0` requires a private Django secret of at least 50 characters, explicit hosts and PostgreSQL. It enables secure cookies, HTTPS redirect, HSTS, verified-contact requirements, staff MFA and a shared database cache for API throttling. Provision `lifealert_throttle_cache` using `manage.py createcachetable` during reviewed deployment. MFA settings/lifetimes and simulation mechanics are in `.env.example`. Proxy trust, cross-origin client setup and edge abuse protection require the actual hosting configuration. DRF throttles are best-effort limits, not a guarantee against distributed attacks. Production `check --deploy` reports the two domain-dependent HSTS subdomain/preload warnings: those flags remain unset until ownership and TLS coverage of the actual domain and subdomains are approved.

Sensitive routine request logging is suppressed; structural audit excludes raw credentials, recordings, full care payloads and precise location. The application API exposes no audit edit/delete action. Database administrators can still alter storage; production needs restricted database roles, tamper-resistant log export, encryption, access reviews, backup/restore tests and monitoring. Hosting, scheduler supervision, incident response, disaster recovery and operational service targets require real infrastructure and named owners.

Client/legal/provider dependencies are listed in the completion matrix. Real billing/store products and signed webhooks, contact/notification providers, EMS partners/jurisdiction, approved service polygons/hours/eligibility, staffing/qualifications, care licensing/transport, release verification, retention/backups and production secrets/storage remain external launch gates. The local implementation makes no HIPAA/COPPA applicability or compliance claim.
