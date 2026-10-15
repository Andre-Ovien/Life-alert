"""Screen-state coverage, without prices or procurement assumptions."""
from pathlib import Path
import csv,json
D=Path(__file__).resolve().parent
screens=json.loads((D/'screens.json').read_text())
state_text=json.loads((D/'states.json').read_text())
rows=[]
for screen in screens:
 for number,state in enumerate(state_text[screen['id']].split('|')):
  rows.append({'state_id':f"{screen['id']}-S{number:02d}",'screen_id':screen['id'],'screen_name':screen['name'],'surface':screen['surface'],'state':state,'trace':screen['trace'],'note':'Base layout' if state=='base' else 'Required design variant/annotation; not a separate product screen'})
assert set(state_text)=={s['id'] for s in screens}
assert len({s['id'] for s in screens})==len(screens)==65
summary={'unique_screens':65,'consumer_screens':46,'operations_screens':19,'consumer_shared_access':6,'consumer_adult':36,'consumer_child':4,'screen_state_entries':len(rows),'additional_named_states':len(rows)-65}
with (D.parents[2]/'SCREEN-STATE-CHECKLIST.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)
(D/'state-register.json').write_text(json.dumps(rows,indent=2)+'\n')
(D/'screen-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
parts=['''# Life alert - complete designer screen list

Draft 0.1 - October 15, 2026. **65 unique screens: 46 consumer Flutter, 19 operations (platform TBD).** No prices or scope reductions. Shared adult access is counted once. States/sheets/components are not additional screens; they still need design coverage. The state checklist is an integral companion.

Consumer: 6 shared adult access + 36 guardian/caregiver + 4 linked child. Operations: 1 staff access + 6 coordinator + 5 administration/routing + 3 responder + 4 accommodation. T02 placement authorization is coordinator-owned; Q06 routing is privileged administration despite its route group.

All screens remain in this complete baseline. M1/M2 in the detailed inventory indicate design sequencing only. There are **502 screen-state entries: 65 default layouts and 437 named variants/conditions**. These are coverage annotations, NOT 502 screens or automatically 502 artboards. The designer should identify separate layouts versus reusable variants explicitly.

''']
for prefix,title in [('A','Shared adult access'),('G','Home and readiness'),('H','Household and caregiver access'),('F','Child care profiles'),('D','Linked devices'),('M','Care recordings'),('B','Subscription and billing'),('I','Help, incidents and temporary care updates'),('S','Settings and support'),('C','Linked child experience'),('O','Staff access - operations platform TBD'),('Q','Coordinator/routing operations - platform TBD'),('R','Responder operations - platform TBD'),('T','Temporary-care operations - platform TBD'),('N','Administration - platform TBD')]:
 parts.append(f'## {title}\n\n| ID | Screen | Required states / variants |\n| --- | --- | --- |\n')
 for item in screens:
  if item['id'].startswith(prefix):parts.append(f"| {item['id']} | {item['name']} | {'; '.join(state_text[item['id']].split('|')[1:])} |\n")
 parts.append('\n')
parts.append('''## Required non-screen deliverables

Reusable accessible help/status/location/audio components; contact/address forms; cancellation REQUEST, revoke-device, unsaved-change, consent/identity, ordinary-call handoff, recording deletion request and privacy/account data-request sheets. Include loading, empty, error/retry, offline/stale, session expiry, revoked access, permission denied and unknown-result patterns where mapped. Include Android/iOS adaptation notes, accessible non-reader alternatives and clickable core journeys. Native OS dialer/payment/permission dialogs are platform handoffs, not invented custom app screens.

Billing B03 explicitly includes failed, cancelled, pending, interrupted, provider-unknown and verified-success results. Restore/reconcile access is conditional on the billing approach selected later. No pricing/vendor is assumed. The child never signs in or seeks parent approval at incident time. Real payment, production identity and live providers remain pending integrations.

Actions, entry/exit, permissions, accessibility, route IDs, sequencing and PRD references are specified in [DESIGNER-HANDOFF.md](DESIGNER-HANDOFF.md). Every state maps to a screen in [SCREEN-STATE-CHECKLIST.csv](SCREEN-STATE-CHECKLIST.csv). Ask the designer to acknowledge included IDs/states and list exclusions. New client workflows may change the labeled baseline later.
''')
(D.parents[2]/'SCREEN-LIST.md').write_text(''.join(parts))
print(json.dumps(summary,indent=2))
