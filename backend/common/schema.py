"""Explicit response contracts for endpoints returning role-scoped projections.

Named request serializers live with their views and are the runtime validators.
The contract exposes no database rows and needs no authenticated sample user.
"""
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

class DeviceScheme(OpenApiAuthenticationExtension):
    target_class='families.authentication.DeviceAuthentication'
    name='childDevice'
    def get_security_definition(self,auto_schema):
        return {'type':'apiKey','in':'header','name':'Authorization',
            'description':'Device <credential>; linked child only. No incident-time adult login.'}

class AdultScheme(OpenApiAuthenticationExtension):
    target_class='common.identity.AdultBearerAuthentication'
    name='adultBearer'
    def get_security_definition(self,auto_schema):return {'type':'http','scheme':'bearer','bearerFormat':'opaque'}

S={'type':'string'}; B={'type':'boolean'}; I={'type':'integer'}
U={'type':'string','format':'uuid'}; T={'type':'string','format':'date-time'}
def nullable(schema):return {**schema,'nullable':True}
def array(schema):return {'type':'array','items':schema}
def obj(**fields):return {'type':'object','properties':fields,'required':list(fields)}
def page(schema):return obj(count=I,next=nullable(S),previous=nullable(S),results=array(schema))
def results(schema):return obj(results=array(schema))
ID_STATE=obj(id=U,state=S)
ID_STATUS=obj(id=U,status=S)
TOKENS=obj(access_token=S,refresh_token=S,token_type=S,access_expires_at=T,refresh_expires_at=T)
NOTE=obj(id=U,author=I,created_at=T,action_taken=S,next_steps=S)
LOCATION=obj(latitude={'type':'number'},longitude={'type':'number'},accuracy_meters={'type':'number'},captured_at=T)
CONTACT=obj(name=S,phone=S,relationship=S)
CARE=obj(name=S,communication=S,support_needs=S,calming_preferences=S,saved_address=S,contacts=array(CONTACT),places=array(obj(label=S,address=S,is_default=B)))
CARE['required']=['name','communication','support_needs','calming_preferences']
PLACEMENT=obj(id=U,incident=U,facility=U,care_place=nullable(U),care=obj(name=S,communication=S,support_needs=S,calming_preferences=S,contacts=array(CONTACT)),state=S,reserved_until=nullable(T),intake_at=nullable(T),released_at=nullable(T),
    current_staff=nullable(I),staff=array(I),authority=nullable(U),transport_reference=S,intake_reference=S,belongings=array(S))
HANDOVER=obj(id=U,kind=S,source=nullable(I),recipient=I,status=S,reference=S,accepted_at=nullable(T))
PUBLIC_STATUS={'type':'object','description':'Truthful, separate response milestones; no arrival-time promise.','additionalProperties':True}
CHILD_INCIDENT=obj(id=U,state=S,review_required=B,cancellation_requested=B,receipt=S,emergency_call_separate=B,public_status=PUBLIC_STATUS)

RESPONSES={
 ('RegisterView','post'):obj(household=U),
 ('SessionView','get'):obj(csrf_token=S,authentication=S),
 ('SessionView','post'):obj(authenticated=B,csrf_token=S),
 ('HealthView','get'):obj(status=S,mode=S,live_emergency_service=B),
 ('ReadinessView','get'):obj(status=S,scope=S,live_service_ready=B),
 ('MobileTokenView','post'):TOKENS,('RefreshView','post'):TOKENS,
 ('ContactChallengeView','post'):obj(status=S,delivery=S),('RecoverView','post'):obj(status=S,delivery=S),
 ('CompleteChallengeView','post'):obj(status=S),
 ('MFAStatusView','get'):obj(enrolled=B),
 ('MFAView','post'):{'oneOf':[obj(secret=S,provisioning_uri=S,expires_at=T),obj(verified=B,valid_until=T),obj(verified=B,valid_until=T,recovery_codes=array(S))]},
 ('SandboxBillingView','create'):obj(id=U,status=S,simulation=B),
 ('PairingConsumeView','post'):obj(id=U,child=U,credential=S,expires_at=nullable(T)),
 ('HouseholdView','entitlement'):obj(active_entitlement=B,starts_at=nullable(T),ends_at=nullable(T),record_available=B,source=nullable(S),accepted_incidents_continue=B,ordinary_emergency_call_separate=B),
 ('ChildView','versions'):page(obj(number=I,created_at=T,author=nullable(I),payload=CARE)),
 ('ChildView','readiness'):obj(care_version=I,profile_fields_set=array(S),contact_count=I,linked_device_count=I,active_entitlement=B,coverage=S,required_care_fields=S,guaranteed_service=B),
 ('IncidentView','acknowledge_notification'):obj(audience=S,delivery=S,acknowledged_at=nullable(T)),
 ('IncidentView','followups'):results(obj(id=U,key=U,location=LOCATION,created_at=T)),
 ('IncidentView','progress'):results(NOTE),
 ('IncidentView','care_placements'):page(obj(id=U,facility=S,state=S,reserved_until=nullable(T),handover_recorded=B,care_authority_recorded=B)),
 ('IncidentView','review_location'):ID_STATUS,('IncidentView','region_handover'):ID_STATUS,
 ('IncidentView','ems_events'):page(obj(event_id=U,state=S,evidence=S,observed_at=T,actor=nullable(I),source=S)),
 ('IncidentView','escalations'):page(obj(id=U,kind=S,status=S,created_at=T,acknowledged_at=nullable(T),resolved_at=nullable(T),resolution_note=S)),
 ('IncidentView','escalation_transition'):ID_STATUS,
 ('IncidentView','offer_team'):obj(id=U,state=S,deadline=T),('IncidentView','ems_evidence'):obj(state=S),
 ('IncidentView','reserve'):ID_STATE,('IncidentView','placement_transition'):ID_STATE,
 ('MyOffersView','list'):results(obj(id=U,incident=U,state=S,deadline=T)),('MyOffersView','transition'):ID_STATE,
 ('RegionHandoverView','list'):page(obj(id=U,incident=U,source_region=U,target=U,status=S,reference=S)),
 ('RegionHandoverView','accept'):ID_STATUS,('RegionHandoverView','decision'):ID_STATUS,
 ('PlacementView','list'):page(PLACEMENT),('PlacementView','retrieve'):PLACEMENT,
 ('PlacementView','assign_staff'):obj(handover=U,status=S),('PlacementView','accept_handover'):ID_STATUS,('PlacementView','handover_decision'):ID_STATUS,
 ('PlacementView','handovers'):page(HANDOVER),('PlacementView','transition'):PLACEMENT,
 ('UnroutedView','list'):results(obj(id=U,location_quality=S,accepted_at=T)),
 ('UnroutedView','route'):obj(id=U,region=U),
 ('PrivacyRequestView','media_hold'):obj(legal_hold=B,retention_until=nullable(T)),
 ('PrivacyRequestView','export'):{'type':'object','description':'Purpose-scoped reviewed export. Account, optional child/contact/place/care-version/media metadata; no audio, credentials, provider raw records or staff private identity.','additionalProperties':True},
}

class ContractSchema(AutoSchema):
    def get_operation_id(self):
        import re
        name=re.sub(r"(?<!^)(?=[A-Z])", "_", self.view.__class__.__name__).lower()
        return name+"_"+self.key()[1]+"_"+self.method.lower()
    def key(self):return (self.view.__class__.__name__,getattr(self.view,'action',self.method.lower()))
    def get_override_parameters(self):
        params=super().get_override_parameters()
        if '{operation}' in self.path:params.append(OpenApiParameter('operation',OpenApiTypes.STR,OpenApiParameter.PATH,enum=['enroll','confirm','verify','disable']))
        if '{purpose}' in self.path:params.append(OpenApiParameter('purpose',OpenApiTypes.STR,OpenApiParameter.PATH,enum=['contact','recovery']))
        if '{id}' in self.path:params.append(OpenApiParameter('id',OpenApiTypes.UUID,OpenApiParameter.PATH))
        if self.view.__class__.__name__=='AuditView':params.append(OpenApiParameter('object_id',OpenApiTypes.UUID,required=True))
        return params
    def _is_list_view(self, serializer=None):
        if self.key() in RESPONSES or self.key() in [('IncidentView','list'),('PlacementView','events'),('IncidentView','location_updates')]:
            return False  # These contracts already include the exact list envelope.
        return super()._is_list_view(serializer)
    def get_request_serializer(self):
        from common.views import RegisterSerializer
        from operations.views import EntitlementSerializer
        from incidents import serializers as incident_serializers
        mapping={('RegisterView','post'):RegisterSerializer,('EntitlementView','create'):EntitlementSerializer,
            ('IncidentView','help'):incident_serializers.HelpSerializer,('IncidentView','transition'):incident_serializers.LifecycleSerializer,
            ('IncidentView','offer_team'):incident_serializers.OfferSerializer,('IncidentView','ems_evidence'):incident_serializers.EMSSerializer,
            ('IncidentView','reserve'):incident_serializers.ReserveSerializer,
            ('IncidentView','placement_transition'):incident_serializers.PlacementTransitionSerializer,
            ('MyOffersView','transition'):incident_serializers.AssignmentTransitionSerializer,
            ('PlacementView','transition'):incident_serializers.PlacementTransitionSerializer}
        if self.key()==('MediaView','upload'):
            from rest_framework import serializers
            from drf_spectacular.utils import inline_serializer
            return inline_serializer('CareAudioUpload',fields={'audio':serializers.FileField()})
        if self.key() in [('MyOffersView','transition'),('PlacementView','transition')]:
            item=mapping[self.key()]()
            item.fields.pop('assignment' if self.key()[0]=='MyOffersView' else 'placement')
            return item
        if self.key() in mapping:return mapping[self.key()]
        if getattr(self.view,'action',None) in ['create','update','partial_update'] and getattr(self.view,'serializer_class',None):
            return self.view.serializer_class()
        return None
    def get_response_serializers(self):
        responses=self.success_responses()
        from drf_spectacular.plumbing import ResolvedComponent
        component=ResolvedComponent(name='APIError',type=ResolvedComponent.SCHEMA,object='LifeAlertAPIError',
            schema={'type':'object','description':'Permission, authentication, validation or throttling error; field keys vary by input.','additionalProperties':True})
        self.registry.register_on_missing(component)
        error=component.ref
        for code in [400,401,403,404,429]:responses.setdefault(code,error)
        return responses
    def success_responses(self):
        key=self.key()
        if key==('IncidentView','progress'):
            return {201:obj(id=U)} if self.method=='POST' else {200:RESPONSES[key]}
        if key==('PlacementView','events'):
            return {201:obj(id=U)} if self.method=='POST' else {200:page(obj(id=U,event_id=U,author=I,kind=S,note=S,created_at=T))}
        if key==('IncidentView','location_updates'):
            minimal=obj(id=U,status=S,quality=S)
            return {201:minimal} if self.method=='POST' else {200:page({'oneOf':[minimal,obj(id=U,status=S,quality=S,location=LOCATION,created_at=T,matched_region=nullable(U),review_reference=S)]})}
        if key==('IncidentView','care'):
            return {200:{'allOf':[CARE,obj(latest_care=nullable(CARE),care_version=nullable(I),latest_version=I,snapshot_is_current=B)]}}
        if key==('IncidentView','response_plan'):
            return {200:{'oneOf':[obj(enabled=B,teams=array(U)),obj(id=U,enabled=B,reviewed_care_version=I,teams=array(U))]}}
        if key==('MediaView','audio'):
            return {(200,'audio/wav'):{'type':'string','format':'binary'}}
        if key==('ReadinessView','get'):return {200:RESPONSES[key],503:RESPONSES[key]}
        if key==('MFAView','post'):return {200:RESPONSES[key],201:RESPONSES[key],204:None}
        if key in [('SessionView','delete'),('MobileLogoutView','post')]:return {204:None}
        if key in RESPONSES:
            status=201 if key in [('RegisterView','post'),('PairingConsumeView','post'),('PlacementView','assign_staff'),('IncidentView','region_handover'),('IncidentView','offer_team'),('IncidentView','reserve')] else 202 if key[0] in ['ContactChallengeView','RecoverView'] else 200
            return {status:RESPONSES[key]}
        value=self.response_serializer()
        if isinstance(value,dict) and all(isinstance(k,int) for k in value):return value
        return {201 if getattr(self.view,"action",None)=="create" else 200:value}
    def response_serializer(self):
        from families.serializers import DeviceSerializer,InvitationSerializer
        from families.lifecycle_views import PairingSerializer
        from incidents.serializers import IncidentSerializer
        key=self.key()
        if key in [('DeviceView','create'),('DeviceView','rotate'),('InvitationView','create'),('PairingView','create')]:
            serializer={ 'DeviceView':DeviceSerializer,'InvitationView':InvitationSerializer,'PairingView':PairingSerializer }[key[0]]
            name={'DeviceView':'credential','InvitationView':'invitation_token','PairingView':'pairing_token'}[key[0]]
            base=self.resolve_serializer(serializer(),'response').ref
            return {201:{'allOf':[base,obj(**{name:S})]}}
        if key[0]=='IncidentView' and key[1] in ['list','retrieve','help','claim','transition','request_cancellation']:
            adult=self.resolve_serializer(IncidentSerializer(),'response').ref
            schema={'oneOf':[adult,CHILD_INCIDENT]}
            if key[1]=='list':schema=page(schema)
            if key[1]=='help':
                return {201:{'type':'object','properties':{'incident':schema,'result':S,'separate_event_review_required':B}},200:{'type':'object','properties':{'incident':schema,'result':S,'separate_event_review_required':B}}}
            return schema
        if key==('EntitlementView','create'):
            from operations.views import EntitlementSerializer
            return {200:EntitlementSerializer()}
        serializer=getattr(self.view,'serializer_class',None)
        if serializer:return serializer()
        return {'type':'object','additionalProperties':True}
