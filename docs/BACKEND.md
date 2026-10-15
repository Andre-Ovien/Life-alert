# Backend foundation and API guide

**Baseline:** October 15, 2026. Read alongside [PRD.md](PRD.md). The human selected Django and future Flutter, authorized sensible backend defaults, and confirmed accepted incidents continue after subscription expiry. Formal client validation and live operating arrangements remain pending.

## What exists

A modular Django REST backend with migrations, authenticated API endpoints, scoped device credentials, household/profile/contact management, private care audio, a local entitlement ledger, transactional incident acceptance, coordinator ownership/progress, independent crew/EMS/notification/placement states and audit events. All integrations are local simulations or manual evidence records. No mobile application, payment processing, outbound messaging or real emergency request is implemented.

Django **5.2.18 LTS** was selected for extended security support and compatibility with installed Python 3.14.6; DRF **3.18.3** and exact dependencies are pinned in `requirements.txt`. Django's [supported-version table](https://www.djangoproject.com/download/) lists 5.2 LTS through April 2028; its [Python compatibility table](https://docs.djangoproject.com/en/5.2/faq/install/) supports Python 3.14 from 5.2.8. See [DRF's official requirements](https://www.django-rest-framework.org/). Recheck security patch releases before deployment.

| Package | Responsibility |
| --- | --- |
| `config` | Settings, URLs, WSGI; local defaults and PostgreSQL environment selection |
| `common` | Structural audit events, registration/session endpoints, no-store responses |
| `families` | Household guardian relationships, child profiles, contacts, device credentials, care media, entitlement ledger |
| `operations` | Disabled-by-default regions, on-duty/available crews, coordinator memberships, facilities, audited config API |
| `incidents` | Atomic services, independent response records, ownership/progress, safe provider adapters and local worker |
| `frontend/` | Flutter/client boundary notes only; no UI scaffold or dependencies |

## Run and authenticate

Follow the root README for the virtual environment and migrations. Run commands from `backend/` so Django's default test discovery finds the application tests. Alternatively use `make test` from the repository root.

1. `GET /api/v1/session/` obtains a CSRF token and cookie.
2. `POST /api/v1/register/` with `username`, `password`, `household_name` and the CSRF token creates a guardian household. It grants no subscription and does not verify legal authority.
3. `POST /api/v1/session/` with `username`, `password` and CSRF token creates an adult session and returns the refreshed token. Use cookies and `X-CSRFToken` for subsequent mutations. `DELETE` logs out.
4. A guardian creates a child, then `POST /api/v1/devices/` with `child` and `label`. The response returns a device `credential` **once**. Store it securely; the database stores only its SHA-256 digest.
5. Child device requests use `Authorization: Device <credential>`. This credential is limited to the linked child and is revocable; it is not a parent session.

An operator can create local accounts with `createsuperuser`; a configuration superuser logs in through the same session endpoint. There is no Django admin site that bypasses the audited configuration API. Ordinary `is_staff` is not sufficient to configure the service, and superuser status alone does not grant child/incident browsing.

Adult native-app authentication, email verification, password recovery, staff MFA, credential rotation/expiry and production abuse prevention are deferred. Current authentication is a local foundation, not a production identity service.

## API inventory

All routes below are relative to `/api/v1/`. UUID identifiers are opaque; obscurity is not authorization. List endpoints normally paginate under `results`. No domain-record DELETE routes are exposed.

| Route | Methods / audience | Purpose |
| --- | --- | --- |
| `households/`, `households/{id}/` | Guardian list/create/read | Own household only; creation links current guardian |
| `children/`, `children/{id}/` | Guardian list/create/read/update | Own profiles; moving children between households unsupported |
| `contacts/`, `contacts/{id}/` | Guardian list/create/read | Emergency contacts; does not grant care/release authority |
| `devices/`, `devices/{id}/` | Guardian list/create/read | Link devices; raw credential returned once |
| `devices/{id}/revoke/` | Guardian POST | Revoke child-device access immediately for subsequent authentication/acceptance |
| `media/`, `media/{id}/` | Authorized list/read; guardian create/update | Purpose/audience metadata and text; no storage URLs |
| `media/{id}/upload/` | Guardian POST multipart `audio` | Validated PCM WAV, at most 5 MiB and 180 seconds; opaque stored filename |
| `media/{id}/audio/` | Authorized GET | Private authenticated stream with no-store response |
| `incidents/help/` | Guardian or linked child POST | Accept eligible help, replay request or register explicit follow-up |
| `incidents/`, `incidents/{id}/` | Scoped GET | Guardian own child, linked device minimal own state, regional coordinator, currently assigned responder |
| `incidents/{id}/care/` | Guardian/coordinator/assigned responder GET | Relevant individual communication/support/calming fields; audited |
| `incidents/{id}/claim-ownership/` | Regional coordinator POST | Acknowledge ownership; received becomes triage; another owner's takeover requires `takeover_reason` |
| `incidents/{id}/progress/` | Regional coordinator GET/POST | Current owner records `action_taken`, `next_steps`; optional `review_completed` clears review flag |
| `incidents/{id}/followups/` | Regional coordinator GET | Request IDs, original timestamps and supplied locations for incident/follow-up reconciliation |
| `incidents/{id}/acknowledge-notification/` | Guardian/coordinator POST | `audience`: own guardian or coordinator audience; acknowledgement is separate from delivery and ownership |
| `incidents/{id}/transition/` | Regional coordinator POST | `target`, optional `outcome`, `reconciled`; disposition requires owner or explicit takeover |
| `incidents/{id}/request-cancellation/` | Guardian/linked child/coordinator POST | Records request; never deletes incident or cancels external response automatically |
| `incidents/{id}/offer-team/` | Regional coordinator POST | `team`, `suitability_confirmed`; on-duty available same-region team, one live offer |
| `my-offers/` | Crew GET | Own offer IDs/deadlines; no child identity before acceptance |
| `my-offers/{assignment}/transition/` | Offered/assigned crew POST | `target`, and `reason` required on decline |
| `incidents/{id}/ems-evidence/` | Regional coordinator POST | `state`, `evidence`; explicit manual record, no actual provider call |
| `incidents/{id}/reserve-placement/` | Regional coordinator POST | `facility`, `authority_reference`, `suitability_confirmed`; atomic capacity check |
| `incidents/{id}/placement-transition/` | Regional coordinator POST | `placement`, `target`, `handover_reference`; records reviewed intake/release/cancellation |
| `configuration/regions/`, `teams/`, `facilities/`, `coordinators/` | Configuration superuser list/create/read/update | Audited configuration; region associations immutable after creation |
| `configuration/entitlements/` | Configuration superuser POST | Local entitlement upsert: `household`, `active`, `starts_at`, `ends_at`; never charges money |
| `configuration/unrouted/` | Configuration superuser GET | Minimal queue of open incidents needing regional routing |
| `configuration/unrouted/{id}/route/` | Configuration superuser POST | `region`, `location_verified`; operator verifies responsibility, retains original location quality |

Example help body (synthetic values only):

```json
{
  "child": "<linked-child-uuid>",
  "request_id": "<new-request-uuid-preserved-for-retries>",
  "location": {
    "latitude": 35.0,
    "longitude": -75.0,
    "accuracy_meters": 20,
    "captured_at": "2026-10-15T10:00:00Z"
  }
}
```

Omit `location` entirely if unavailable. A supplied location must have all four fields. Device responses contain minimal incident state/receipt/review flags; they expose no responder instructions, location, family contacts or coordinator identity. Adult incident responses show independent crew, EMS, placement and notification statuses. HTTP receipt/201 is never an arrival or dispatch guarantee. Ordinary emergency calling belongs to the future native device calling pathway, separate from paid APIs; there is no server endpoint pretending to place an emergency call.

## Transactional acceptance and entitlement

Acceptance and local entitlement updates lock the **household first**. Device revocation uses the same household-first lock and rechecks the device credential under that lock. PostgreSQL therefore serializes entitlement changes, revocation and acceptance for a household.

- An authorized `(child, request_id)` replay with the identical normalized location returns its original incident, including after expiry. Changed location with the same ID is rejected; retain the initial request ID/payload across retries.
- New request IDs require current `active` entitlement and `starts_at <= server time < ends_at`.
- A unique partial database constraint permits **one open incident per child**. A different request ID during an open incident records a durable request with its supplied location, returns `followup_requires_review`, sets `review_required` and writes an audit event. Coordinator follow-up inspection is available. It does not silently start or claim independent dispatch for a second emergency.
- **Limitation:** truly separate simultaneous emergencies and meaningful location changes need human reconciliation. Follow-up location is retained but does not automatically replace original routing or assign another crew. Automated separate-event management and push re-alerting are deferred.
- Accepted incident + two independent notification jobs + EMS handoff record + request mapping + audit are committed together. No parent acknowledgement gates this transaction or later crew/EMS work.
- Accepted incidents continue after entitlement expiry; a new paid request cannot. Current entitlement renewal is reflected separately. `CONTINUE_ACCEPTED_INCIDENTS=1` is the human-confirmed default. Setting it to `0` only reports `policy_review_required`; it **does not stop accepted care**. Any different operational policy needs reviewed implementation.
- Network failure or outside coverage never changes billing state. Missing/uncertain location is accepted for manual routing review when entitlement is active. Fresh coordinates outside all enabled pilot regions return an explicit coverage error without creating a paid incident. Retries of accepted requests still work if configuration changes.

The billing adapter reads a local ledger only. Webhook verification, event ordering/reconciliation, plan products, charges/refunds and real provider integration remain unimplemented. All future ledger writers must use the household-lock service boundary.

## Exact independent states

### Incident lifecycle and accountable ownership

| From | To | Required meaning/check |
| --- | --- | --- |
| `received` | `triage` | Coordinator claims review/ownership; records owner identity |
| `triage` | `active` | Coordinator activates response, or crew accepts an offer |
| `active` | `resolved` | Owner records nonempty outcome; response branches completed/reconciled; `reconciled=true` |
| `received`, `triage` | `cancelled` | Coordinator disposition; any already-started response must follow reviewed cancellation checks |
| `active` | `cancelled` | Prior cancellation request, owner disposition, nonempty outcome and reconciled response branches |

`response_started_at` is independent of lifecycle state: an offer, EMS operation/evidence or placement can start while the incident is still received/triage. Once set, closure requires all assignments to be complete/declined/timed_out, all placements released/cancelled, and EMS closed/no_dispatch. Early closure explicitly closes an unstarted EMS task. Incident state never changes solely from parent notification acknowledgement.

**Confirmed human responsibility:** the coordinator actively works on a solution, acknowledges ownership, arranges appropriate response, records actions/next steps and follows through to verified handover/resolution. Notification alone is neither ownership nor resolution. Current owner creates progress notes; another regional coordinator may claim ownership with an explicit takeover reason. Production supervisor escalation and staffing remain pending.

No accommodation is required to resolve an incident. The outcome must explain assistance provided, actual care/caregiver handover or approved disposition, known EMS outcome and follow-up ownership. The foundation enforces a nonempty narrative plus branch reconciliation; **it does not validate real-world identity, handover evidence or the truth/completeness of the narrative**. Structured handover, follow-up tasks and exceptional care decisions require further work before production.

### Crew

`offered → accepted → en_route → arrived → complete`; `offered → declined` requires a reason; unaccepted `offered → timed_out` occurs when the local worker runs after the configured deadline. Acceptance checks team membership, deadline, on-duty/current availability and atomic incident ownership. Accepted teams become unavailable; completion does not automatically declare them ready again.

Only on-duty available regional teams with a coordinator suitability confirmation receive offers. Skills/qualifications are configurable metadata; automatic qualification matching and travel-time ranking are not implemented. A qualified team may decline because availability changed, equipment/transport failed or a support mismatch was discovered. Decline/timeout flags human review; **automatic next-team offers, interruption/reassignment, coordinator acknowledgement deadlines and backup/supervisor notifications are deferred**. The intended fallback chain is in the PRD; the backup policy remains proposed/configurable. No accepted crew means no “on the way” status.

### EMS

`handoff_pending` is a coordinator task. In a simulated region the worker changes it to `provider_acknowledged`, or `unknown` on a simulated timeout. Neither is contact or dispatch.

Manual evidence transitions:

- `handoff_pending`, `provider_acknowledged`, `unknown` → `contact_confirmed` or `closed`; pending/acknowledged can also become `unknown`.
- `contact_confirmed` → `dispatch_confirmed`, `no_dispatch` or `closed`.
- `dispatch_confirmed` → `arrived` or `closed`; `arrived`/`no_dispatch` → `closed`.

Every manual transition requires coordinator-provided evidence and is audited. `closed` records reconciled disposition, not an assertion that EMS was cancelled. Unknown outcomes are never blindly retried. Evidence history is partially represented by audit state changes; a production evidence ledger preserving every provider payload/reference is still needed. There is no live provider selection or callable real EMS adapter.

### Notification and placement

Notification delivery state: `queued → simulated` in local worker. Reserved future delivery outcomes: `delivered`/`failed`. `acknowledged_at`/`acknowledged_by` are separate fields. Coordinator acknowledgement does not claim ownership. Recipient/channel delivery, retries and provider callbacks are deferred.

Placement: `reserved → intake → released` or `reserved → cancelled`. Facility locks prevent over-capacity reservations across incidents; one live placement per incident. Coordinator records authority/suitability and handover references. Facilities default disabled/capacity zero. The model reserves staff relations but staff assignment API, suitability automation, transport, detailed care events, reservation expiry, recipient identity verification and licensing/consent review are deferred. A reference is evidence asserted by an authorized operator, not independently verified legal consent.

## Location, security and operational limits

Location values must be finite, geographically bounded and timestamped with accuracy. Development defaults: freshness **300 seconds**, accuracy **200 meters**, future-time tolerance **30 seconds**; these are configurable local test assumptions, not client-approved thresholds. Stale/inaccurate/missing/ambiguous location requires review, with any saved address explicitly labeled as fallback. Only a single enabled matching region is auto-selected. Region rectangles are provisional; no GIS, route estimates, geocoding or travel times exist. Production service polygons need PostGIS or an approved equivalent. Care endpoints currently return the latest profile; immutable incident care-version snapshots and caregiver invitation/verified authority workflows are deferred.

The configuration admin's minimal unrouted queue allows verified regional handoff without giving every coordinator global child access. Global duty ownership and real notification for unrouted incidents must be established before launch. No automated routing from an unverified saved address is performed.

Private media has no public URL and is streamed after audience/object authorization. Children see only comfort-authorized media; responders see instruction-authorized media only during assigned active response; coordinators see relevant responder media for their open regional incidents. Adult guardians manage their own family. Sensitive reads/mutations are audited; API responses use `Cache-Control: private, no-store`. File content is restricted to validated WAV in this foundation; arbitrary uploads are rejected. Storage cleanup/retention, malware controls, encrypted managed storage, backup policy and streaming revocation/cache policy need production design. Disk encryption/encrypted media storage are not provisioned by this repository.

Audit events store actor/device IDs and controlled structural facts, not care details, precise locations, audio or raw credentials. Progress/outcome/evidence records are sensitive domain data. No list/delete audit API is exposed. Database operators can still alter audit rows; immutable external audit storage and tamper detection are pending. Operational traces must not record authorization headers, bodies or private response content.

Django session/CSRF controls and object filtering enforce role boundaries. Region coordinator/team membership is configured by a privileged operator; legal guardian verification and qualified staffing remain external obligations. Production requires reviewed identity flows, staff MFA, TLS/proxy settings, secret management, monitoring/redaction, retention, incident recovery, deployment hardening and jurisdiction/legal review. No HIPAA/COPPA applicability or compliance is asserted.

## PostgreSQL configuration and verification

SQLite local exploration requires no server. It does **not** provide PostgreSQL row-lock behavior and is unsuitable for concurrent incident/capacity operations. Production should use PostgreSQL; no PostGIS extensions are required by these initial models.

Export `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` before running migrations/tests. The test user must be allowed to create a separate Django test database. Never run tests against real child data or a live operations database.

```sh
cd backend
../.venv/bin/python manage.py test
../.venv/bin/python manage.py check
../.venv/bin/python manage.py makemigrations --check --dry-run
```

Tests cover entitlement/replay/follow-up semantics, cross-family and regional/device/crew access, revocation, location failure/coverage, explicit lifecycle/cancellation/reconciliation, provider receipt/timeout, care-media audience access, coordinator ownership, capacity and release authority boundaries, CSRF and audited configuration. PostgreSQL-only thread tests exercise same-key retries, distinct-key acceptance serialization, entitlement expiry racing acceptance and competing capacity reservations; these skip under SQLite. Final validation results are recorded below.

`process_work` is a synchronous local simulation processor. It locks open incidents before processing local jobs and can be rerun without repeating completed logical work. It has no scheduler, live queue/leases, actual delivery, provider retries or uptime promise. A production worker must claim jobs with leases, use external idempotency keys outside database transactions, recover failures and reconcile ambiguous outcomes. Timers only progress while this command runs.

For isolated local PostgreSQL verification, `make test-postgres` uses existing `initdb`/`pg_ctl` executables to create a temporary socket-only cluster under ignored `.runtime/`, runs the complete suite, then stops and removes that generated cluster. It does not connect to or alter existing databases/services. Installing a PostgreSQL server is optional for SQLite exploration.

## Public status contract

Adult and linked-child incident responses include `public_status.code` and a reassuring `message`. Codes reflect evidence: `request_received`, `coordinator_review`, `contacting_response_team` (offer actually sent), `team_assigned` (acceptance), `team_en_route`, `team_arrived`, `resolved`, `cancelled`. A follow-up creation response overrides its message to `followup_requires_review`; ordinary incident retrieval still describes the original incident's team, not an independently dispatched second event. Simulated EMS/notification receipts cannot produce team travel status. The client's proposed 5–10 minute mobilization target remains pending staffing/coverage and milestone validation; no ETA/SLA is returned or enforced.

## Validation record — October 15, 2026

- Full isolated PostgreSQL run: **35 tests passed**, including four concurrency/transaction tests. Temporary server stopped and generated cluster removed afterward.
- Local SQLite run: **31 tests passed, 4 PostgreSQL-only tests skipped**.
- Local migrations applied; Django system checks, migration drift check and dependency consistency check passed. The safe local worker command completed with no outbound activity.
- Original project symlink still resolves to this SSD repository; documents and backend files are accessible through both paths.
- `check --deploy` intentionally reports six warnings under local settings: development secret/debug, local HTTP redirect/cookies and unset HSTS. A non-debug environment requires a private secret and enables secure cookies/redirect; TLS/HSTS/proxy/deployment review is still required. This is not deployment-ready emergency infrastructure.
- No commits, pushes, deployments, real payment operations, outbound messages, emergency calls or mobile screens were created.

These checks validate backend behavior against synthetic data, not real staffing, response times, provider authority, legal care consent or field safety.
