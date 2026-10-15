# Backend completion audit

Updated October 15, 2026. The controllable backend scope from PRD v0.2 is implemented using simulations, explicit configuration and protected manual evidence. This is a software completion record, not an operational launch approval.

The published baseline is `bebe4a97be12300482514ddd6fad3e35ebdb9ea4` in `Andre-Ovien/Life-alert`. The subsequent backend implementation and documentation are tracked on [`codex/response-workflow-reliability`](https://github.com/Andre-Ovien/Life-alert/tree/codex/response-workflow-reliability) for GitHub review. Mobile UI and designer/PRD PDF snapshots are unchanged by this backend phase.

## Requirement evidence

| PRD / capability | Implemented behavior | Verification source | External dependency / deliberate boundary |
| --- | --- | --- | --- |
| FAM-01 | Household isolation; CSRF cookie sessions; hashed opaque adult access/refresh, rotation/replay revocation, verified-contact and recovery contracts | `incidents/tests.py`, `common/test_identity.py` | Real contact delivery, production identity operation and account support |
| FAM-02 | Recipient-bound one-use caregiver invitation, six explicit rights, expiry/revocation; separate authority evidence/review | `families/test_care.py` | Actual relationship/identity/authority verification procedure |
| CARE-01 | Individual communication, support, calming preferences, contacts and saved places; unknown fields are not diagnosed/inferred | `families/test_care.py` | Approved required care fields, eligibility and data taxonomy |
| CARE-02 | Optimistic version checks, immutable care versions, incident snapshot and separately labeled latest care | `families/test_care.py`, `incidents/test_evidence.py` | Client review of operational care-change protocols |
| MEDIA-01 | Separate child comfort/responder instruction audiences and text alternatives; active assignment/placement scope | `incidents/tests.py`, `incidents/test_care_operations.py` | Approved content and offline/native caching policy |
| MEDIA-02 | Private authenticated audio, no public storage paths, no-store, bounded complete PCM WAV validation, archived access denial, retained replacement blobs and reviewed purging | `common/test_privacy.py`, `incidents/tests.py` | Managed encrypted storage/backup deletion, malware/content scanning requirements beyond format validation, legal retention |
| DEV-01 | Household-locked credential revocation/replacement, recipient-scoped device link, one-use expiring pairing | `families/test_lifecycle.py`, `incidents/tests.py` | Actual hardware, native secure storage and physical loss/re-pairing support |
| DEV-02 | Scoped child help without fresh parent login or staff MFA; expiry/revocation rechecked at acceptance | `incidents/tests.py`, `common/test_mfa.py` | Supported device calling/connectivity/accessibility behavior |
| READY-01 | Profile/device/contact/subscription facts, explicitly unevaluated coverage/required fields and no service guarantee | `families/test_lifecycle.py` | Reviewed coverage hours, polygons, eligibility and operational availability inputs |
| SUB-01 | Household-locked server eligibility, acceptance-time evidence, accepted-care continuity; idempotent normalized sandbox event revisions/stale/conflict handling | `incidents/tests.py`, `families/test_lifecycle.py` | Billing authority, plans/prices, signed live events, store rules, refunds/grace policy |
| SUB-02 | Explicit independent ordinary-call indication; no fake server call/dispatch endpoint | `incidents/tests.py`, API contract | Native calling capabilities and truthful platform handling |
| INC-01, INC-03 | Incident/request/care snapshot/notification work/EMS record/audit persist atomically; parent response never gates other branches | `incidents/tests.py`, `incidents/test_workflow.py` | Actual providers and a supervised scheduler |
| INC-02 | Request UUID replay, payload mismatch rejection, concurrency uniqueness, explicit follow-up review with original observation data | `incidents/tests.py`, `incidents/test_evidence.py` | Separate simultaneous emergencies require coordinator reconciliation under the stated PRD rule |
| INC-04 | Receipt, human acknowledgement, owner, offer, acceptance, en-route, arrival and EMS evidence remain distinct; public status follows facts | `incidents/tests.py`, `incidents/test_workflow.py` | Real recipient delivery/evidence and approved status wording |
| INC-05, INC-06 | Atomic crew acceptance; declines/timeouts; reviewed ordered candidate fallback; ownership/backup escalation; explicit exhaustion tasks | `incidents/test_response_policy.py`, `incidents/test_workflow.py` | Approved suitable teams, staffing, qualifications, primary/backup, timeouts and operating hours |
| INC-07, INC-08 | Cancellation request separate from disposition; current owner, branch/task reconciliation, narrative and structured outcome, handover/EMS/follow-up details | `incidents/tests.py`, `incidents/test_workflow.py` | Real cancellation protocol, truth of handover evidence and human follow-through |
| INC-09 | Child/family/region/assignment isolation, independent sibling incidents, immutable acceptance snapshot and attributed transition evidence | `incidents/tests.py`, `families/test_care.py` | Approved history/access-retention rules |
| LOC-01, LOC-02 | Freshness/accuracy, labeled fallback, ambiguous/unrouted review, idempotent observations, explicit location review; named accepted regional transfer with decline/cancel | `incidents/tests.py`, `incidents/test_evidence.py` | Reviewed real geography/maps, remote-jurisdiction handoff and offline relevance thresholds |
| Reliability | Durable jobs/attempts, leases/fencing, bounded retries, crash receipt reconciliation, independent branch progress, obsolete alert cancellation, persistent task ownership | `incidents/test_workflow.py`, PostgreSQL races | Live channel adapters, verified external reconciliation and monitoring/on-call operation |
| EMS boundary | Simulator acknowledgement/unknown only; append-only idempotent manual evidence distinguishing contact/dispatch; replay cannot regress current state | `incidents/tests.py`, `incidents/test_evidence.py` | Approved EMS partner, jurisdiction, access/authority and real dispatch evidence |
| ACC-01, ACC-02 | Disabled/default reviewed facilities/places, suitability assertion, atomic capacity/place reservation, configured pre-intake expiry and persistent no-capacity task | `incidents/test_care_operations.py`, `incidents/tests.py` PostgreSQL capacity race | Actual suitable/licensed facilities, capacity feeds and reservation policy |
| ACC-03 | Placement/release require current verified purpose/subject authority, external review reference and validity | `incidents/test_care_operations.py`, `families/test_care.py` | Legally valid consent/authority and approved exceptions; software asserts no legal determination |
| ACC-04 | Named staff, accepted intake handover, relevant care snapshot, transport/intake references, intake time and belongings | `incidents/test_care_operations.py` | Physical transport, arrival/identity verification and approved care protocols |
| ACC-05 | Accountable shift ownership until named acceptance; decline/cancel replacement; idempotent attributed support/observation/handover events | `incidents/test_care_operations.py` | Staffing ratios, clinical/medication scope and actual care delivery |
| ACC-06 | Matching current release authority/recipient, explicit evidence/time and reconciled staff handover; ended care access removed | `incidents/test_care_operations.py` | Real recipient identity verification and release approval procedure |
| ACC-07 | Capacity/expiry/handover failure tasks, accountable owner, no fabricated placement; no automatic discharge during intake | `incidents/test_care_operations.py` | Approved alternatives, maximum stay, overnight model, fees and transport |
| Staff security | Encrypted TOTP enrollment, replay-resistant verification/recovery codes, per-session step-up, production role enforcement; child independence | `common/test_mfa.py` | Production secret/key lifecycle, staff onboarding/recovery and security assessment |
| Audit/admin | Audited configuration, regional/purpose restrictions, exact-object structural audit read permission; no audit mutation API | `common/test_operations.py`, scope tests above | Restricted database roles, immutable external log retention, role/access review |
| Privacy | Reviewed request/export/correction/archive/purge, immutable decision history, unknown-policy/legal-hold retention, adult closure safeguards and session revocation | `common/test_privacy.py` | Applicable legal rights/deadlines, complete statutory disclosure, storage/backups/native cache deletion and retention approval |
| API/health/config | Validated OpenAPI requests/role projections, pinned dependencies/migrations, no-secret readiness failures; production secret/host/PostgreSQL/TLS/cookie/cache/MFA guards | `common/test_contract.py`, `common/test_operations.py`, `make check`, `make schema` | Hosting, TLS/proxy setup, cache provisioning, scheduler, backups/restore, monitoring and operational SLOs |

## Verification record

Final verification after the last source changes:

- `make test-postgres`: **128 tests passed**, including all nine PostgreSQL concurrency cases; isolated cluster stopped and removed.
- `make test`: **128 tests passed with nine intentional PostgreSQL-only skips**.
- `make check`: no Django issues, no migration drift and no broken dependency requirements.
- `make schema`: OpenAPI validation passed with zero warnings/errors; **107 paths / 155 operations** and explicit adult-bearer, child-device and cookie authentication schemes. Role-scoped response samples validate against the schema.
- `git diff --check`: passed. Flutter source, PRD source and PDF snapshots have no changes in this phase.
- Production configuration check with ephemeral synthetic settings: no errors; two HSTS subdomain/preload warnings remain for the actual domain/TLS deployment decision. No real database or provider was contacted by this configuration check.

 PostgreSQL tests exercise concurrency using isolated connections, including acceptance/idempotency, assignment/capacity, work claims, stale workers, optimistic care edits, device pairing and response policy ticks. The SQLite suite is a local portability check; its PostgreSQL-only race cases are intentionally skipped.

No real EMS request, outbound notification, payment, provider credential, deployment or publication was used. Privacy purge tests operate only on temporary synthetic files. The local media purge command was not applied to application media.

## External launch decisions

These require actual client authority, provider access or infrastructure; fabricated values would not satisfy the PRD:

1. Operating organization, supported ages/eligibility, service jurisdictions/polygons/hours, named primary/backup and staffed availability. Define the proposed 5–10 minute mobilization target before treating it as a promise.
2. Crew qualifications/suitability protocol, actual duty/availability updates, approved timing/retry/escalation owners, separate-emergency and offline replay review policy.
3. Notification/contact delivery channels, verified recipients, real device capabilities and secure native credential/media handling.
4. EMS partner and jurisdiction access, permitted contact method, evidence/reconciliation contract and human dispatch/cancellation protocol.
5. Billing provider/store agreements, products/prices, signed authoritative event mapping, refunds/cancellation/grace and unknown-billing policy.
6. Care licensing/model, actual places/capacity, legal consent/authority exceptions, staff/transport responsibility, release verification, stay/overnight/fees and care-specific records.
7. Qualified privacy/child-protection/licensing review, actual retention/hold/access policy, full disclosure scope, cloud/backups/cache erasure and incident response. No HIPAA/COPPA applicability/compliance is asserted.
8. Production secrets and rotation, hosting/TLS/proxy, encrypted media/database/backups, shared cache provisioning, scheduler supervision, tamper-resistant audit export, monitoring, restore/recovery exercises and independent security/release assessment.

The local backend provides the mechanisms and truthful boundaries needed to configure those choices. It does not claim real-world staffing, authority, delivery, dispatch, placement availability or compliance from a simulated test result.
