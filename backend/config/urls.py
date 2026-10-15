from django.urls import path, include
from rest_framework.routers import DefaultRouter
from common.views import RegisterView, SessionView, HealthView
from families.views import HouseholdView, ChildView, DeviceView, ContactView, MediaView
from incidents.views import IncidentView, MyOffersView
from operations.views import RegionView, TeamView, FacilityView, CoordinatorView, EntitlementView, UnroutedView

router = DefaultRouter()
for prefix, view, basename in [
    ('households',HouseholdView,'household'), ('children',ChildView,'child'),
    ('devices',DeviceView,'device'), ('contacts',ContactView,'contact'), ('media',MediaView,'media'),
    ('incidents',IncidentView,'incident'), ('my-offers',MyOffersView,'offer'),
    ('configuration/regions',RegionView,'region'), ('configuration/teams',TeamView,'team'),
    ('configuration/facilities',FacilityView,'facility'), ('configuration/coordinators',CoordinatorView,'coordinator'),
    ('configuration/entitlements',EntitlementView,'entitlement'), ('configuration/unrouted',UnroutedView,'unrouted'),
]:
    router.register(prefix,view,basename=basename)
urlpatterns = [path('api/v1/',include(router.urls)), path('api/v1/register/', RegisterView.as_view()),
               path('api/v1/session/', SessionView.as_view()), path('health/',HealthView.as_view())]
