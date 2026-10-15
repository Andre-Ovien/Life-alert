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
OUT = HERE.parents[1] / 'Life-alert-Flutter-Screen-Design-Handoff-v0.1.pdf'
FONT_DIR = Path('/Users/macbook/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype')
for name, file in [('Body','LiberationSans-Regular.ttf'),('Strong','LiberationSans-Bold.ttf'),('Italic','LiberationSans-Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT_DIR/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Strong',italic='Italic',boldItalic='Strong')
W,H=595.28,841.89
M=42; CW=W-2*M
NAVY='#142D3A'; INK='#243E4A'; MUTED='#526873'; TEAL='#126B67'; MINT='#EAF4F0'; PAPER='#FAFBF9'; LINE='#D8E2E1'; SAND='#F7EFE0'; AMBER='#855D19'; BLUE='#EDF2F7'
c=canvas.Canvas(str(OUT),pagesize=(W,H),pageCompression=1)
c.setTitle('Life alert | Complete Flutter Screen Design Handoff')
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
    text('LIFE ALERT',M,29,9,TEAL,'Strong');text('FLUTTER SCREEN DESIGN / DRAFT 0.1',285,29,8,MUTED)
    line([(M,53),(W-M,53)],LINE,.7)
    text(kicker.upper(),M,71,9,TEAL,'Strong')
    title_size=min(27,26*CW/pdfmetrics.stringWidth(title,'Strong',27))
    para(title,M,93,CW,title_size,NAVY,True,leading=30,maxh=31)
    para(subtitle,M,135,CW,10.5,MUTED,maxh=34)
    footer(n)


def footer(n):
    line([(M,790),(W-M,790)],LINE,.7)
    text('Design structure only | Client validation pending | 15 OCT 2026',M,805,8,MUTED)
    text(f'{n:02d} / 18',W-M-35,805,8,TEAL,'Strong')


def end():c.showPage()


import json
S=json.loads((HERE/"screens.json").read_text())
ST=json.loads((HERE/"states.json").read_text())
BY={s["id"]:s for s in S}

def inventory(n,kicker,title,ids,note):
    page(n,kicker,title,note)
    rh=76 if len(ids)<=7 else 68
    for i,sid in enumerate(ids):
        s=BY[sid];y=185+i*rh
        rect(M,y,CW,rh-7,MINT if i%2==0 else '#FFFFFF',LINE,r=6)
        para(sid+'  '+s['name'],M+12,y+9,143,10.5,NAVY,True,leading=13,maxh=rh-27)
        cap={'F':'CORE','M':'MIXED','P':'PLANNED'}[s['api'][0]]
        text(s['phase']+' / '+cap,M+12,y+rh-20,8.5,TEAL,'Strong')
        candidates=ST[sid].split('|')[1:]
        # Each screen's complete states live in the linked CSV; show critical
        # examples here rather than burying readable names in a dense grid.
        special={'B03':'failed; cancelled; pending; interrupted; unknown; verified success; restore if applicable',
          'B01':'expired; no plan data; accepted incident after expiry',
          'I02':'unconfirmed send; offline; retry; old queued request',
          'C03':'unconfirmed; received; assigned; en-route; follow-up',
          'I07':'no capacity; authority unresolved; intake; release'}
        variants=special.get(sid,'; '.join(candidates[:3]))
        content=s['purpose']+'<br/><font color="'+MUTED+'">States: '+variants+'.</font>'
        para(content,M+174,y+9,CW-187,9.8,leading=12.8,maxh=rh-18)
    para('CORE = foundation contract; MIXED = gaps; PLANNED = missing API. No finished UI. Full route/action/access detail: DESIGNER-HANDOFF.md; all states: SCREEN-STATE-CHECKLIST.csv.',M,746,CW,9.2,MUTED,maxh=32)
    end()

# 01
c.bookmarkPage('p1');c.addOutlineEntry('Complete screen design handoff','p1',0)
c.setFillColor(HexColor(PAPER));c.rect(0,0,W,H,fill=1,stroke=0)
rect(0,0,W,363,NAVY,r=0)
text('FLUTTER / SCREEN ARCHITECTURE + DESIGNER HANDOFF',M,48,9,'#A6D5CE','Strong')
text('Life alert',M,96,50,'#FFFFFF','Strong')
para('The complete screen list.<br/>Clear journeys. Clear boundaries.',M,174,CW,24,'#FFFFFF',leading=32)
pill('DRAFT 0.1 / DESIGN PLANNING',M,277)
text('65 PURPOSEFUL SCREENS',M,400,25,NAVY,'Strong')
box(M,452,247,121,'46 consumer screens','6 shared adult access<br/>36 guardian / caregiver<br/>4 linked child experience',MINT)
box(306,452,247,121,'19 operations screens','Coordinator, crew, care and administration. Platform TBD; separate from consumer navigation.',BLUE)
box(M,608,CW,87,'No surprise state omissions','Payment failure, offline delivery, permissions, revocation and care authority are explicitly mapped to their owning screens. Variants and sheets are not automatically new screens.',small=True)
para('<b>Current code:</b> bounded Django foundation plus a non-operational Flutter route/contract scaffold. No finished UI, live authentication, payment, messaging or emergency service is delivered by these placeholders.',M,722,CW,10.5,MUTED,maxh=44)
footer(1);end()
# 02
page(2,'01 / Information architecture','Separate roles. One coherent service.','Confirmed consumer Flutter surfaces; staff platform and operational implementation remain open decisions.')
box(M,181,CW,65,'Shared adult access - A01 to A06','Sign-in, registration, verification and recovery are counted once. Production mobile identity remains planned.',BLUE,small=True)
line([(298,246),(298,271)],arrow=True)
box(M,271,CW,66,'Parent / authorized caregiver - 36 screens','Home, children, incidents and settings anchor navigation. Scoped caregiver rights differ from guardian authority.',MINT,small=True)
for x,t,b in [(42,'HOME','G / H / B'),(174,'CHILDREN','F / D / M'),(306,'INCIDENTS','I'),(438,'SETTINGS','S')]:
    box(x,367,115,69,t,b,small=True)
line([(298,337),(298,352)]);line([(99,352),(495,352)])
for x in [99,231,363,495]:line([(x,352),(x,367)],arrow=True)
box(M,478,247,138,'Linked child - C01 to C04','Guardian setup happens beforehand. Help home, simple request status and optional comfort content. No incident-time login or parent approval.',MINT,small=True)
box(306,478,247,138,'Separate operations - 19 screens','O / Q / R / T / N inventory is retained for coordination, response, care and administration. Do not add staff tabs to the consumer app.',BLUE,small=True)
para('<b>Permission rule:</b> a caregiver invitation or emergency-contact entry is not legal authority to place or release a child. Object access, region and assignment still apply to every deep link.',M,664,CW,11,maxh=62)
para('M1/M2 labels indicate suggested design sequencing only. Both remain in the complete consumer list; no scope reduction or price is assumed.',M,744,CW,9.5,MUTED,maxh=30)
end()
# 03-14: Complete screen catalogue.
inventory(3,'02 / Shared access','Access, verification and recovery',[f'A{i:02d}' for i in range(1,7)],'6 shared screens. Linked-child emergency initiation never goes through these adult access gates.')
inventory(4,'03 / Adult home + household','Home and caregiver permissions',['G01','G02','G03','H01','H02','H03','H04'],'7 screens. Invitation/grant/authority verification is planned; current guardian records are not that full workflow.')
inventory(5,'04 / Child profiles','Individual care information',['F01','F02','F03','F04','F05'],'5 screens. Tailor communication, support and calming information to the person, never diagnosis stereotypes.')
inventory(6,'05 / Device + media','Devices and recording audiences',['D01','D02','D03','D04','M01','M02','M03'],'7 screens. Protected adult setup leads to restricted child access; no raw long-lived credential belongs in a design.')
inventory(7,'06 / Subscription + billing','Plans, renewal and payment outcomes',['B01','B02','B03','B04'],'4 screens. B03 contains explicit failed-payment and other result variants; vendor and pricing remain unselected.')
inventory(8,'07 / Settings + support','Account, privacy and assistance',['S01','S02','S03','S04','S05'],'5 screens. Data deletion/export, production account changes and support channels remain planned, not instant promises.')
inventory(9,'08 / Parent help + live response','Ask for help and see what is known',['I01','I02','I03','I04'],'4 screens. Child/incident location is authoritative; a remote parent location must not silently replace it.')
inventory(10,'09 / History + temporary care','Outcomes, care updates and authority',['I05','I06','I07','I08'],'4 screens. Capacity, suitability, consent and verified recipient authority govern care and release.')
inventory(11,'10 / Linked child experience','A simple, individually accessible path',['C01','C02','C03','C04'],'4 screens. Use non-reader/assistive alternatives and optional comfort audio; never expose staff-only information.')
inventory(12,'11 / Coordinator operations','Own the incident. Arrange help.',['O01','Q01','Q02','Q03','Q04','Q05','Q06'],'7 screens. Platform TBD. Q06 is privileged routing, not permission for every coordinator to browse global children.')
inventory(13,'12 / Crew + care operations','Response and temporary-care handover',['R01','R02','R03','T01','T02','T03','T04','T05'],'8 screens. Platform TBD. T02 authorization is coordinator-owned; other care screens require appropriate staff access.')
inventory(14,'13 / Administration','Configure scope with an audit trail',['N01','N02','N03','N04'],'4 screens. Admin configuration status alone does not permit unrestricted child-content access.')
# 15 - Critical interaction
page(15,'14 / Critical interaction','Help is independent of parent approval','The child flow is C02 -> C03; adult context is I01 -> I02 -> I03. Child setup C01 precedes incidents.')
box(155,183,285,67,'Help action -> delivery feedback','No required parent confirmation, reading puzzle or hidden approval barrier.',MINT,small=True)
line([(298,250),(298,274)],arrow=True)
box(155,274,285,68,'Durable receipt is a distinct event','Before server confirmation: show unconfirmed delivery. Retry the same request ID.',small=True)
line([(298,342),(298,367)]);line([(120,367),(475,367)])
for x in [120,298,475]:line([(x,367),(x,394)],arrow=True)
box(M,394,157,151,'PARENT','Notify parent/contacts.<br/><br/>Delivery and human acknowledgement are separate. No acknowledgement gate.',MINT,small=True)
box(219,394,157,151,'ORGANIZATION','Coordinator claims ownership and arranges suitable response. Crew acceptance is explicit.',small=True)
box(396,394,157,151,'EMS / HANDOFF','Configured regional workflow. Receipt is not confirmed contact or dispatch.',BLUE,small=True)
box(M,578,247,133,'Truthful reassurance','Received -> actual crew offer -> crew accepts -> en-route evidence.<br/><br/>Only en-route permits "on the way".',MINT,small=True)
box(306,578,247,133,'Unknown is not success','Offline, timeout, stale location or unknown EMS outcome stays visible.<br/><br/>Another request may need review, not separate dispatch.',SAND,AMBER,small=True)
para('One open incident per child is a current foundation limit. A different request ID records follow-up review. Cancellation is a request; external response may continue pending coordinator reconciliation.',M,738,CW,10,MUTED,maxh=39)
end()
# 16 - Continuity and care
page(16,'15 / Continuity + care gates','Do not lose the child between states','Subscription, coverage, connectivity and actual operational response are separate facts.')
box(M,181,247,107,'NEW paid request','Requires current entitlement. Billing success alone is not verified access; coverage and request eligibility remain separate.',small=True)
box(306,181,247,107,'ALREADY accepted incident','Continues through resolution after expiry. New paid requests need renewed entitlement. Offline/out-of-area does not cancel billing.',MINT,small=True)
text('TEMPORARY-CARE JOURNEY - I07 / I08 + OPERATIONS T01-T05',M,324,9,TEAL,'Strong')
for i,(t,b) in enumerate([('1  Suitability + capacity','No appropriate place -> coordinator alternatives.'),('2  Authority + reservation','Consent/authority must be verified; no assumed guardianship.'),('3  Intake + accountable care','Staff, approved transport and relevant care handover.'),('4  Authorized release','Verify recipient identity/authority and record handover.')]):
    y=356+i*83;box(M,y,CW,64,t,b,MINT if i%2 else '#FFFFFF',small=True)
    if i<3:line([(298,y+64),(298,y+83)],arrow=True)
para('<b>Closure:</b> record actual assistance, verified handover/disposition, known EMS outcome and follow-up ownership. Reconcile outstanding branches. No temporary care needed does not itself close the incident.',M,709,CW,10.5,maxh=49)
end()
# 17 - Foundation
page(17,'16 / Actual Flutter foundation','Structure now. Finished designs later.','The scaffold is real source code, but every product screen is a labeled non-operational placeholder.')
box(M,180,CW,72,'frontend/mobile','Android/iOS Flutter project; 46 consumer route contracts in grouped features, with a shared placeholder rather than copied screen widgets.',MINT,small=True)
for i,(t,b) in enumerate([('APP + ROUTING','Router parser/delegate;<br/>demo persona guard;<br/>back-stack reset'),('CORE BOUNDARIES','Scoped access contracts;<br/>API abstraction;<br/>network disabled'),('FEATURES + SHARED','10 grouped features;<br/>incident evidence models;<br/>shared presentation')]):box(M+i*176,289,159,151,t,b,small=True)
text('MEANINGFUL FOUNDATION CHECKS',M,477,9,TEAL,'Strong')
box(M,505,CW,100,'Analyzed and tested on the installed SDK','Flutter 3.44.1 / Dart 3.12.1. Static analysis and 10 unit/widget/navigation tests passed, including narrow-device large text, role isolation and evidence-based copy.',MINT,small=True)
box(M,631,CW,96,'What this does not claim','No real authentication, credentials, child data, backend calls, billing, messages, dialer calls or EMS integration. Staff platform remains TBD. Backend features were not changed.',BLUE,small=True)
para('Native device readiness is separate: Android license review is outstanding. No app was installed on a phone. See frontend/mobile/README.md for reproducible checks and build limitations.',M,747,CW,9.5,MUTED,maxh=30)
end()
# 18 - Delivery
page(18,'17 / Handoff checklist','What the designer should return','No prices or assumed exclusions. Ask for a complete response against stable IDs and required variants.')
checks=[('Complete screen list','Acknowledge all 46 consumer and 19 separate operations IDs, with explicit sequencing and any exclusions.'),('State coverage','Map loading, empty, error, offline, permissions, unknown outcomes and the screen-specific states in the CSV.'),('Critical variants','Show failed/cancelled/pending/interrupted billing, child unconfirmed send, expiry during accepted care, revoked devices and authority failure.'),('Reusable design system','Accessible controls, status/location/audio components and purposeful sheets. Do not multiply screens for every repeated state.'),('Android + iOS adaptation','Document native handoffs, typography, safe areas, assistive semantics, large text and platform differences.'),('Clickable journeys + source','Prototype child and adult help, uncertainty, device setup, care handover and account/billing recovery. Deliver editable annotated files.')]
for i,(t,b) in enumerate(checks):
    y=183+i*76;rect(M,y,CW,66,MINT if i%2==0 else '#FFFFFF',LINE,r=6)
    para(t,M+12,y+12,151,10.5,NAVY,True,maxh=41)
    para(b,M+181,y+10,CW-194,10,leading=13.2,maxh=44)
box(M,669,CW,65,'Use the full companion set','SCREEN-LIST.md: names and states. DESIGNER-HANDOFF.md: per-screen route/action/access/trace. SCREEN-STATE-CHECKLIST.csv: every state mapped to an owner.',BLUE,small=True)
para('502 checklist entries = 65 base layouts + 437 named conditions, not 502 screens or automatic artboards. Client/provider changes require versioned agreement. The proposed 5-10 minute mobilization goal is not an ETA or guarantee.',M,750,CW,9.5,MUTED,maxh=32)
end()
c.save();print(OUT)
