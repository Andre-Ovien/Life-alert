from drf_spectacular.views import SpectacularAPIView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from common.operations_views import AuditView,ReadinessView
from common.mfa_views import MFAView,MFAStatusView
from common.identity_views import MobileTokenView,RefreshView,MobileLogoutView,ContactChallengeView,RecoverView,CompleteChallengeView
from common.privacy_views import PrivacyRequestView,RetentionPolicyView
from common.views import RegisterView, SessionView, HealthView
from families.views import HouseholdView, ChildView, DeviceView, ContactView, MediaView
from families.lifecycle_views import PairingView,PairingConsumeView,SandboxBillingView
from families.extended_views import GrantView,InvitationView,PlaceView,AuthorityView
from incidents.care_views import PlacementView
from incidents.views import IncidentView, MyOffersView,RegionHandoverView
from operations.views import CarePlaceView,FacilityStaffView,ResponsePolicyView,RegionView, TeamView, FacilityView, CoordinatorView, EntitlementView, UnroutedView

router = DefaultRouter()
for prefix, view, basename in [
    ('audit-events',AuditView,'audit-event'),
    ('privacy-requests',PrivacyRequestView,'privacy-request'),('configuration/retention-policies',RetentionPolicyView,'retention-policy'),
    ('device-pairing',PairingView,'device-pairing'),('configuration/billing-events',SandboxBillingView,'billing-event'),
    ('caregiver-grants',GrantView,'caregiver-grant'), ('caregiver-invitations',InvitationView,'caregiver-invitation'),
    ('places',PlaceView,'place'), ('authorities',AuthorityView,'authority'),
    ('households',HouseholdView,'household'), ('children',ChildView,'child'),
    ('devices',DeviceView,'device'), ('contacts',ContactView,'contact'), ('media',MediaView,'media'),
    ('placements',PlacementView,'placement'),
    ('region-handovers',RegionHandoverView,'region-handover'),
    ('incidents',IncidentView,'incident'), ('my-offers',MyOffersView,'offer'),
    ('configuration/care-places',CarePlaceView,'care-place'),('configuration/facility-staff',FacilityStaffView,'facility-staff'),
    ('configuration/response-policies',ResponsePolicyView,'response-policy'),
    ('configuration/regions',RegionView,'region'), ('configuration/teams',TeamView,'team'),
    ('configuration/facilities',FacilityView,'facility'), ('configuration/coordinators',CoordinatorView,'coordinator'),
    ('configuration/entitlements',EntitlementView,'entitlement'), ('configuration/unrouted',UnroutedView,'unrouted'),
]:
    router.register(prefix,view,basename=basename)
urlpatterns = [path('api/v1/schema/',SpectacularAPIView.as_view()),path('api/v1/mobile/mfa/',MFAStatusView.as_view()),path('api/v1/mobile/mfa/<str:operation>/',MFAView.as_view()),path('api/v1/device-pairing/consume/',PairingConsumeView.as_view()),path('api/v1/mobile/token/',MobileTokenView.as_view()),path('api/v1/mobile/refresh/',RefreshView.as_view()),
    path('api/v1/mobile/logout/',MobileLogoutView.as_view()),path('api/v1/mobile/contact-challenges/',ContactChallengeView.as_view()),
    path('api/v1/mobile/recovery/',RecoverView.as_view()),path('api/v1/mobile/challenges/<str:purpose>/complete/',CompleteChallengeView.as_view()),path('api/v1/',include(router.urls)), path('api/v1/register/', RegisterView.as_view()),
               path('api/v1/session/', SessionView.as_view()), path('health/',HealthView.as_view()),path('health/ready/',ReadinessView.as_view())]
