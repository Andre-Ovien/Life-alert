"""Editable client/designer PRD. Uses bundled ReportLab; no backend dependencies.
Run with the bundled Python runtime from any directory. Vector diagrams are
native PDF shapes/lines; no Mermaid renderer or remote assets are required.
"""
from pathlib import Path
from math import atan2, cos, sin, pi
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'Life-alert-Client-Designer-PRD-v0.2.pdf'
FONT_DIR = Path('/Users/macbook/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype')
for name, file in [('Body','LiberationSans-Regular.ttf'),('Strong','LiberationSans-Bold.ttf'),('Italic','LiberationSans-Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT_DIR/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Strong',italic='Italic',boldItalic='Strong')
W,H=595.28,841.89
M=42; CW=W-2*M
NAVY='#142D3A'; INK='#243E4A'; MUTED='#526873'; TEAL='#126B67'; MINT='#EAF4F0'; PAPER='#FAFBF9'; LINE='#D8E2E1'; SAND='#F7EFE0'; AMBER='#855D19'; BLUE='#EDF2F7'
c=canvas.Canvas(str(OUT),pagesize=(W,H),pageCompression=1)
c.setTitle('Life alert | Client and Designer Product Requirements')
c.setAuthor('Life alert project team')
c.setSubject('Review baseline - product flow, experience boundaries and launch decisions')


def rect(x,y,w,h,fill=white,stroke=None,r=10):
    c.setFillColor(HexColor(fill) if isinstance(fill,str) else fill)
    c.setStrokeColor(HexColor(stroke or fill) if isinstance(stroke or fill,str) else stroke or fill)
    c.setLineWidth(.7)
    c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=bool(stroke))


def text(s,x,y,size=11,color=INK,font='Body'):
    c.setFillColor(HexColor(color));c.setFont(font,size);c.drawString(x,H-y-size*.82,s)


def para(s,x,y,w,size=11,color=INK,bold=False,leading=None,maxh=None):
    style=ParagraphStyle('p',fontName='Strong' if bold else 'Body',fontSize=size,leading=leading or size*1.4,textColor=HexColor(color),spaceAfter=0)
    p=Paragraph(s,style); _,h=p.wrap(w,1000)
    if maxh is not None and h>maxh+.1:
        raise ValueError(f'Text overflow {h:.1f}>{maxh:.1f}: {s[:85]}')
    p.drawOn(c,x,H-y-h)
    return h


def line(points,color=TEAL,width=1.4,dashed=False,arrow=False):
    c.setStrokeColor(HexColor(color));c.setLineWidth(width)
    c.setDash(4,3) if dashed else c.setDash()
    p=c.beginPath();p.moveTo(points[0][0],H-points[0][1])
    for x,y in points[1:]:p.lineTo(x,H-y)
    c.drawPath(p)
    c.setDash()
    if arrow:
        a,b=points[-2],points[-1];theta=atan2(b[1]-a[1],b[0]-a[0]);n=5
        p=c.beginPath();p.moveTo(b[0],H-b[1])
        for ang in [theta+pi*.83,theta-pi*.83]:p.lineTo(b[0]+n*cos(ang),H-(b[1]+n*sin(ang)))
        p.close();c.setFillColor(HexColor(color));c.drawPath(p,fill=1,stroke=0)


def pill(s,x,y,kind='confirmed'):
    color,fill={'confirmed':(TEAL,MINT),'proposed':(AMBER,SAND),'pending':(MUTED,BLUE),'deferred':(AMBER,SAND)}[kind]
    w=pdfmetrics.stringWidth(s,'Strong',8)+18
    rect(x,y,w,21,fill,r=5);text(s,x+9,y+6,8,color,'Strong')
    return w


def box(x,y,w,h,title,body='',fill='white',accent=TEAL,small=False):
    if fill=='white':fill='#FFFFFF'
    rect(x,y,w,h,fill,LINE)
    rect(x,y,3,h,accent,r=1)
    sz=11.5 if small else 13
    compact = h < 85
    th=para(title,x+15,y+(10 if compact else 14),w-30,sz,NAVY,True,maxh=h-20)
    if body:para(body,x+15,y+(14 if compact else 22)+th,w-30,9.8 if small else 10.5,leading=13.7 if small else 14.5,maxh=h-th-(19 if compact else 33))


def band(y,title,body,fill=MINT):
    box(M,y,CW,76,title,body,fill)


def page(n,kicker,title,subtitle):
    c.setFillColor(HexColor(PAPER));c.rect(0,0,W,H,fill=1,stroke=0)
    c.bookmarkPage(f'p{n}');c.addOutlineEntry(title,f'p{n}',0)
    text('LIFE ALERT',M,29,9,TEAL,'Strong');text('CLIENT + DESIGNER / REVIEW BASELINE',285,29,8,MUTED)
    line([(M,53),(W-M,53)],LINE,.7)
    text(kicker.upper(),M,71,9,TEAL,'Strong')
    para(title,M,93,CW,27,NAVY,True,leading=30,maxh=31)
    para(subtitle,M,135,CW,10.5,MUTED,maxh=34)
    footer(n)


def footer(n):
    line([(M,790),(W-M,790)],LINE,.7)
    text('Working title | Client validation pending | 15 OCT 2026',M,805,8,MUTED)
    text(f'{n:02d} / 13',W-M-35,805,8,TEAL,'Strong')


def end():c.showPage()

# 01 - Cover
c.bookmarkPage('p1');c.addOutlineEntry('Life alert - review baseline','p1',0)
c.setFillColor(HexColor(PAPER));c.rect(0,0,W,H,fill=1,stroke=0)
rect(0,0,W,386,NAVY,r=0)
text('PRODUCT REQUIREMENTS / CLIENT + DESIGNER EDITION',M,47,9,'#A6D5CE','Strong')
text('Life alert',M,94,51,'#FFFFFF','Strong')
para('A coordinated path from<br/>asking for help to care handover.',M,165,490,23,'#FFFFFF',leading=30)
pill('REVIEW BASELINE v0.2',M,252)
# Rendered service loop on cover
for x,title,sub in [(42,'Ask for help','Child or parent'),(219,'Coordinate care','Organization + crew'),(396,'Verify handover','Authorized support')]:
    rect(x,303,157,56,'#254553',r=8);text(title,x+12,316,11,'#FFFFFF','Strong');text(sub,x+12,337,9,'#BBD9D5')
line([(199,331),(219,331)],'#8CCBC0',1.6,arrow=True);line([(376,331),(396,331)],'#8CCBC0',1.6,arrow=True)
text('THE PRODUCT',M,423,9,TEAL,'Strong')
para('Individual care. Clear responsibility.',M,449,CW,25,NAVY,True,leading=30)
para('A US-based subscription service for parents, caregivers and children with disabilities. Family-provided care information supports organizational response and temporary care when appropriate.',M,498,CW,12,leading=18,maxh=80)
box(M,593,CW,98,'What this edition is for','Align the client on the service journey and decisions. Give the designer clear actors, information boundaries, status language and flows. Detailed API contracts remain in the companion technical baseline.',MINT)
para('<b>Current position:</b> Django backend foundation with simulated providers. Future Android/iOS app: Flutter. Mobile screens, live integrations and operating arrangements are pending.',M,716,CW,10.5,MUTED,maxh=50)
footer(1);end()

# 02 - Executive scope
page(2,'01 / Product intent','The service at a glance','A paid care-response service built around each child, with accountable human coordination.')
for x,t,b in [(42,'Know the child','Care preferences, communication methods and calming approaches are individual. A diagnosis never defines ability.'),(219,'Respond together','A linked child or parent can request help. Parent notification runs alongside organizational response and configured EMS escalation.'),(396,'Complete the handover','Temporary care is considered when appropriate. Follow through until an authorized handover or reviewed disposition is recorded.')]:
    box(x,188,157,167,t,b,small=True)
text('CONFIRMED HUMAN DIRECTION',M,387,9,TEAL,'Strong')
box(M,413,247,132,'Product choices','Paid new requests require entitlement. Already accepted incidents continue after expiry. Child help has no incident-time parent approval gate.',MINT)
box(306,413,247,132,'Technology choices','Django backend first. Flutter for future Android/iOS. Mobile UI waits for client payment and designer screens.',MINT)
box(M,573,CW,82,'Service boundaries','No confirmed continuous sensor surveillance, universal coverage or guaranteed crew, ambulance, transport or care place. Coverage hours and staffing still need client confirmation.',SAND,AMBER)
text('READ THE LABELS',M,690,9,TEAL,'Strong')
pill('CONFIRMED',M,713);pill('PROPOSED',210,713,'proposed');pill('PENDING',378,713,'pending')
para('Human-agreed baseline;<br/>client validation pending.',M,742,155,9.5,MUTED,maxh=35)
para('Recommended target or<br/>safeguard for review.',210,742,155,9.5,MUTED,maxh=35)
para('Client decision or operating<br/>dependency still required.',378,742,175,9.5,MUTED,maxh=35)
end()

# 03 - Roles
page(3,'02 / Actors + permissions','The right information, per role','Access follows household, assignment, region and purpose. Being a contact alone grants no care authority.')
roles=[('Parent / guardian','Manage own household, care profile, contacts, recordings and linked devices.','Cannot manage other families or approve staff actions by default.'),('Child / linked device','Ask for help independently; view minimal own request status and permitted comfort audio.','No family administration or responder-only instructions.'),('Regional coordinator','Claim ownership, arrange response, record actions and next steps, reconcile handover.','Authorized regional incidents only; notification is not ownership.'),('Assigned response crew','Accept offered work; read relevant incident location, care information and instruction audio.','No unrestricted child browsing; access ends with assignment.'),('Temporary-care staff','Intended access: necessary placement care, intake and authorized release information.','Staff workflows and verified care authority need further delivery.'),('Configuration administrator','Configure regions, crews, coordinators, facilities and local entitlements with audit.','Admin status alone does not grant child/incident browsing.')]
for i,(t,can,limit) in enumerate(roles):
    x=M+(i%2)*264;y=185+(i//2)*174
    box(x,y,247,151,t,can+'<br/><br/><font color="'+MUTED+'">'+limit+'</font>',fill=MINT if i<2 else '#FFFFFF',small=True)
box(M,717,CW,53,'Shared boundary: protect sensitive child information','Secure media, revocable devices, object-level controls and an audit trail are required.',BLUE,small=True)
end()

# 04 - Onboarding
page(4,'03 / Family setup','Prepare once. Ask for help simply.','Parent-linked child access is the baseline; child self-registration has not been agreed.')
steps=[('01  Create the family account','Establish guardian access and household ownership.'),('02  Add the child care profile','Communication, support needs, sensory and calming preferences.'),('03  Record contacts + authority','Distinguish emergency contacts from authorized care/release recipients.'),('04  Add purpose-labeled audio','Choose comfort, responder instructions or explicitly both.'),('05  Link the device + check readiness','Revocable child credential; entitlement and coverage shown separately.')]
for i,(t,b) in enumerate(steps):
    y=186+i*106;box(M,y,291,84,t,b,small=True)
    if i<4:line([(187,y+84),(187,y+106)],arrow=True)
box(354,186,199,224,'Design for this child','Offer alternatives to reading or speaking. Use simple controls and clear feedback. Account for assistive technology, sensory needs and individual preferences.<br/><br/>Do not infer capabilities from a diagnosis.',MINT,small=True)
box(354,440,199,254,'Readiness is a set of facts','<b>Identity:</b> device linked?<br/><br/><b>Payment:</b> entitlement active?<br/><br/><b>Coverage:</b> area supported?<br/><br/><b>Care:</b> information current?<br/><br/>Enrollment is not a guarantee of operational availability.',small=True)
para('<b>Designer boundary:</b> no login or parental confirmation at the child\'s incident-time help action. Device linking happens beforehand.',M,745,CW,10.5,TEAL,maxh=30)
end()

# 05 - Parallel response
page(5,'04 / Request + response','One request. Parallel response paths.','Parent acknowledgement never gates organizational response or configured EMS escalation.')
box(150,179,295,64,'Child or parent asks for help','Linked child control has no incident-time login or parent approval.',MINT,small=True)
line([(298,243),(298,261)],arrow=True)
box(150,261,295,64,'Eligible request is durably received','Credential, entitlement and location context checked; incident ID returned.',small=True)
line([(298,325),(298,351)])
line([(120,351),(475,351)])
for center in [120,298,475]:line([(center,351),(center,380)],arrow=True)
text('PARALLEL RESPONSE - NO PARENT APPROVAL GATE',42,334,8,TEAL,'Strong')
box(42,380,157,218,'PARENT + CONTACTS','Notify the parent and configured contacts.<br/><br/>Track delivery separately from human acknowledgement.<br/><br/>Unreachable parent does not pause other response paths.',MINT,small=True)
box(219,380,157,218,'ORGANIZATION','Alert coordinator.<br/><br/>Offer suitable available crew.<br/><br/>Crew accepts explicitly; decline or timeout prompts review.<br/><br/>Coordinator works on a solution.',small=True)
box(396,380,157,218,'EMS / HANDOFF','Apply configured regional escalation protocol.<br/><br/>Coordinator-led handoff or approved provider, when arranged.<br/><br/>Receipt is not contact or confirmed dispatch.',BLUE,small=True)
band(627,'Honest feedback at every stage','Received, assigned and en-route are different facts. Current development providers simulate outcomes; no real notifications or emergency calls are made.')
para('<b>Location:</b> route from the child/incident, with accuracy and freshness. Saved addresses are labeled fallbacks. Unknown location requires human review.',M,729,CW,10.5,MUTED,maxh=42)
end()

# 06 - States
page(6,'05 / Evidence + status','A status must describe a real event','Keep incident lifecycle separate from notifications, crew response, EMS and temporary-care placement.')
xs=[42,176,310,444]
for x,t,b in zip(xs,['RECEIVED','TRIAGE','ACTIVE','RESOLVED'],['Eligible request saved','Coordinator owns review','Response activated','Outcome + handover']):
    box(x,184,109,72,t,b,MINT,small=True)
for x in xs[:-1]:line([(x+109,220),(x+134,220)],arrow=True)
rect(176,286,150,43,SAND,LINE);text('CANCELLED',194,300,11,AMBER,'Strong')
line([(96,256),(96,307),(176,307)],AMBER,arrow=True)
line([(230,256),(230,286)],AMBER,arrow=True)
line([(365,256),(365,307),(326,307)],AMBER,arrow=True)
para('After response starts:<br/>request + coordinator review<br/>+ branch reconciliation.',383,276,169,9.5,AMBER,maxh=49)
text('INDEPENDENT EVIDENCE TRACKS',M,358,9,TEAL,'Strong')
lanes=[('CREW',['Offer created','Team accepts','Confirmed en-route'],MINT),('EMS',['Contact confirmed','Dispatch confirmed','Arrival confirmed'],BLUE),('PLACEMENT',['Suitable capacity','Authority confirmed','Intake / release'],MINT)]
for i,(name,labels,fill) in enumerate(lanes):
    y=391+i*87;text(name,M,y+22,10,TEAL,'Strong')
    for j,label in enumerate(labels):
        x=156+j*136;rect(x,y,124,60,fill,LINE)
        para(label,x+10,y+18,104,10,NAVY,True,maxh=34)
        if j<2:line([(x+124,y+30),(x+136,y+30)],arrow=True)
box(M,669,CW,82,'Notification delivery is not human acknowledgement','A delivered alert does not mean someone owns the incident. A provider receipt does not confirm EMS dispatch. Assignment acceptance does not mean a crew is already travelling.',SAND,AMBER)
end()

# 07 - Coordination
page(7,'06 / Accountable human response','The coordinator works on the solution','Confirmed responsibility: acknowledge ownership, arrange response and follow through to verified resolution.')
for i,(t,b) in enumerate([('01  Own the incident','Explicitly acknowledge responsibility; an alert alone does not do this.'),('02  Arrange appropriate response','Review location and needs; select suitable available support.'),('03  Record actions + next steps','Keep a clear operational trail and follow-up ownership.'),('04  Verify handover + disposition','Reconcile crew, EMS and any placement work before closure.')]):
    y=186+i*119;box(M,y,291,94,t,b,small=True)
    if i<3:line([(187,y+94),(187,y+119)],arrow=True)
pill('PROPOSED FALLBACK SAFEGUARD',354,186,'proposed')
box(354,225,199,133,'Crew declines / no acknowledgement','Require decline reason or expire the offer using an approved configurable deadline.',SAND,AMBER,small=True)
line([(453,358),(453,389)],AMBER,arrow=True)
box(354,389,199,120,'Coordinator review + next offer','Alert the responsible coordinator while arranging the next eligible crew.',SAND,AMBER,small=True)
line([(453,509),(453,540)],AMBER,dashed=True,arrow=True)
box(354,540,199,122,'Backup / supervisor','If primary coordinator remains unresponsive, use the client-approved backup chain. Staffing and timings pending.',SAND,AMBER,small=True)
box(M,704,CW,63,'Foundation boundary','Manual offers, explicit ownership, progress notes and offer expiry exist. Automatic next-team/backup routing and live delivery are deferred.',BLUE,small=True)
end()

# 08 - Care journey
page(8,'07 / Temporary care','Temporary care, verified handover','Temporary accommodation is considered when appropriate; purchase does not guarantee a place.')
items=[(42,186,'01  Check suitability + capacity','Coordinator reviews child needs and a suitable available facility.'),(319,186,'02  Verify authority + consent','Confirm who may authorize placement and under which operating authority.'),(319,353,'03  Reserve place + assign staff','Avoid double allocation. Verify staff suitability and responsibility.'),(42,353,'04  Arrange transport + intake','Approved transport, relevant care instructions, belongings and intake record.'),(42,520,'05  Provide temporary care','Document accountable staff handovers and necessary care events.'),(319,520,'06  Verify authorized release','Check recipient identity/authority and record final care handover.')]
for x,y,t,b in items:box(x,y,234,134,t,b,MINT if t.startswith(('01','06')) else '#FFFFFF',small=True)
line([(276,253),(319,253)],arrow=True)
line([(436,320),(436,353)],arrow=True)
line([(319,420),(276,420)],arrow=True)
line([(159,487),(159,520)],arrow=True)
line([(276,587),(319,587)],arrow=True)
box(M,696,CW,72,'No place available? No authority? Escalate to the coordinator.','Keep responsibility visible and arrange approved alternatives. No temporary care needed? Still record assistance, verified handover and open-response reconciliation before resolving.',SAND,AMBER,small=True)
end()

# 09 - Audio + designer
page(9,'08 / Care content + interaction','Two recording audiences','A single file may serve both purposes only when its audience access is explicitly chosen.')
box(172,183,251,68,'Parent-provided care recording','Purpose + audience + text alternative',MINT,small=True)
line([(298,251),(298,275)]);line([(167,275),(428,275)])
line([(167,275),(167,307)],arrow=True);line([(428,275),(428,307)],arrow=True)
box(M,307,247,166,'CHILD COMFORT','Familiar voice, calming message or individually helpful reassurance.<br/><br/>Linked child device can access permitted comfort content. Playback does not mean an alert was sent.',MINT,small=True)
box(306,307,247,166,'RESPONDER INSTRUCTIONS','Communication tips, relevant support and care preferences.<br/><br/>Assigned responders and authorized staff receive necessary instructions, not unrestricted family media.',BLUE,small=True)
text('DESIGN THE EXPERIENCE AROUND EVIDENCE',M,507,9,TEAL,'Strong')
box(M,534,247,146,'Accessible help action','Simple, understandable controls. Alternatives to reading/speaking. Individually appropriate feedback. Recover from duplicate taps without creating parallel incidents.',small=True)
box(306,534,247,146,'Reassuring status copy','"Your request was received."<br/>"A team has accepted your request."<br/>"Your team is on the way" only after confirmed en-route status.',small=True)
para('<b>Privacy boundary:</b> no public audio URLs. Scope access by household, assignment and purpose. Revocation, retention, consent and secure storage require reviewed policies.',M,718,CW,10.5,MUTED,maxh=47)
end()

# 10 - Subscription
page(10,'09 / Entitlement + continuity','Payment controls new paid requests','Human-confirmed baseline: continue already accepted incidents through resolution after expiry.')
box(M,183,234,78,'ALREADY ACCEPTED INCIDENT','Accepted while eligible; same request ID on retry.',MINT,small=True)
box(319,183,234,78,'NEW PAID REQUEST','New request ID; verify current entitlement.',small=True)
line([(159,261),(159,302)],arrow=True)
box(M,302,234,154,'Continue the accepted response','Expiry does not abandon care. Preserve the incident and follow through to handover/resolution.<br/><br/>A retry replays the original accepted result; it is not a new paid incident.',MINT,small=True)
# Decision diamond
center=(436,340);dx=79;dy=52
p=c.beginPath();p.moveTo(center[0],H-(center[1]-dy));p.lineTo(center[0]+dx,H-center[1]);p.lineTo(center[0],H-(center[1]+dy));p.lineTo(center[0]-dx,H-center[1]);p.close()
c.setFillColor(HexColor(BLUE));c.setStrokeColor(HexColor(TEAL));c.drawPath(p,fill=1,stroke=1)
para('Current active<br/>entitlement?',390,324,92,11,NAVY,True,maxh=35)
line([(436,261),(436,288)],arrow=True)
line([(436,392),(436,436)],arrow=True);text('YES',445,408,8,TEAL,'Strong')
box(319,436,234,102,'Check coverage + accept eligibility','Persist eligible request. Missing/stale location requires review; entitlement alone is not a crew or care-place guarantee.',MINT,small=True)
line([(515,340),(566,340),(566,616),(553,616)],AMBER,arrow=True);text('NO',539,356,8,AMBER,'Strong')
box(319,579,234,92,'Restrict the new paid request','Explain entitlement status. Renewal is needed for new paid service; the accepted incident still continues.',SAND,AMBER,small=True)
box(M,496,234,175,'Keep these facts separate','<b>Subscription:</b> payment entitlement.<br/><br/><b>Coverage:</b> operating service area.<br/><br/><b>Connectivity:</b> delivery capability.<br/><br/>Coverage/network loss does not cancel billing.',small=True)
box(M,711,CW,58,'Ordinary emergency calling remains separate','Available through the supported device calling pathway, independent of paid organization service.',BLUE,small=True)
end()

# 11 - Roadmap
page(11,'10 / Build direction','Django first. Flutter later.','The current foundation validates backend behavior with synthetic data and simulated integrations.')
pill('DEFERRED INTERFACE',M,181,'deferred')
box(M,215,CW,72,'Future Flutter app / Android + iOS','Guardian experience and scoped child help experience. Build after client payment and designer screens.',SAND,AMBER,small=True)
line([(298,287),(298,318)],arrow=True)
rect(M,318,CW,187,MINT,LINE)
text('DJANGO + DJANGO REST FRAMEWORK',M+17,336,11,TEAL,'Strong')
for i,(t,b) in enumerate([('FAMILY + ACCESS','Profiles, devices,<br/>care media'),('RESPONSE','Entitlements, incidents,<br/>ownership, crew states'),('CARE + AUDIT','Regions, placement,<br/>controlled records')]):
    box(59+i*165,373,147,109,t,b,small=True)
line([(298,505),(298,530)]);line([(120,530),(475,530)])
for ctr in [120,298,475]:line([(ctr,530),(ctr,552)],arrow=True)
for x,t,b in [(42,'BILLING','Local ledger;<br/>no payments'),(219,'NOTIFICATIONS','Simulation;<br/>no outbound delivery'),(396,'EMS / HANDOFF','Simulation/manual record;<br/>partner unselected')]:box(x,552,157,100,t,b,BLUE,small=True)
text('DELIVERY SEQUENCE',M,687,9,TEAL,'Strong')
for i,(t,b) in enumerate([('1  Align','Client service model'),('2  Foundation','Backend + test contracts'),('3  Design + app','Flutter, when authorized'),('4  Limited pilot','Only after launch gates')]):
    x=M+i*132;text(t,x,713,10,TEAL,'Strong');para(b,x,736,119,9.5,MUTED,maxh=30)
end()

# 12 - Decisions
page(12,'11 / Client review + launch gates','Decisions the client must supply','These choices can be configured; they must be validated before the affected live service launches.')
decisions=[('Operating model + authority','Who provides care, coordination, transport and accommodation? What legal/operational authority applies?'),('Pilot region + coverage','Which US areas and hours? Which ages/support needs are eligible? What service is actually available?'),('Staffing + escalation ownership','Who owns coordination and response? Qualifications, backup coverage, approved timeouts and handover responsibilities?'),('Care capacity + authorization','Which facilities, places, staffing and maximum stays? Who can authorize placement and release?'),('EMS + communications','Which emergency partner/process serves each region? Supported devices/channels? Who confirms contact and dispatch?'),('Commercial + privacy policies','Pricing, grace/cancellation/refunds; validate continuity. Consent, retention, access, deletion and applicable legal review?')]
for i,(t,b) in enumerate(decisions):box(M+(i%2)*264,184+(i//2)*166,247,145,t,b,small=True)
box(M,704,CW,64,'Launch gate: approval plus operational readiness','No live service until staffing, authority, privacy, provider arrangements, recovery and truthful service claims are reviewed. Purchase alone guarantees none of these.',SAND,AMBER,small=True)
end()

# 13 - Acceptance and handoff
page(13,'12 / Acceptance + design handoff','What a ready experience must prove','Use these scenarios in review. Technical test detail remains in the companion backend guide.')
rows=[('Independent child help','No incident-time login or parental approval. Parent, organization and configured EMS branches are independent.'),('Duplicates + uncertain location','Retries do not duplicate response. New events and stale/missing location need review. No connectivity means delivery is unconfirmed.'),('Honest reassurance','Receipt, acknowledgement, assignment, en-route and EMS dispatch are distinct evidence milestones.'),('Responsible continuity','Expiry blocks new paid requests while accepted care continues. Coordinator owns follow-through.'),('Care + privacy boundaries','Only authorized audiences access care/audio. Placement and release require suitability, authority and handover.'),('Failure handling','Nobody accepts? Provider times out? Keep uncertainty and ownership visible; do not invent success.')]
for i,(t,b) in enumerate(rows):
    y=185+i*71;rect(M,y,CW,61,MINT if i%2==0 else '#FFFFFF',LINE,r=6)
    para(t,M+12,y+12,157,10.5,NAVY,True,maxh=40)
    para(b,M+184,y+10,CW-198,10,INK,leading=13.5,maxh=43)
box(M,630,CW,70,'Review + change control','Record each client change with affected journey/requirement, impact, approval and version. Update this visual PRD and the technical baseline together; formal client sign-off is pending.',BLUE,small=True)
para('<b>Measure separately:</b> receipt-to-acknowledgement, ownership, assignment, en-route, arrival and verified handover. The proposed 5-10 minute mobilization goal needs client validation and a defined milestone; it is not an ETA or guarantee.',M,720,CW,10,INK,leading=13.5,maxh=42)
end()
c.save()
print(OUT)
