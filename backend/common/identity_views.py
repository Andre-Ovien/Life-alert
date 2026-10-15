from drf_spectacular.utils import extend_schema
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed,PermissionDenied
from families.access import is_device
from . import identity
from .models import AdultTokenSession

class PublicIdentityView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    throttle_classes=[ScopedRateThrottle]
    throttle_scope='identity'

class MobileTokenViewPostInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)

class MobileTokenView(PublicIdentityView):
    @extend_schema(request=MobileTokenViewPostInput, methods=["POST"])
    def post(self,request):
        Input = MobileTokenViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        return Response(identity.issue_tokens(**s.validated_data,request=request))

class RefreshViewPostInput(serializers.Serializer):
    refresh_token = serializers.CharField(min_length=20, max_length=200)

class RefreshView(PublicIdentityView):
    @extend_schema(request=RefreshViewPostInput, methods=["POST"])
    def post(self,request):
        Input = RefreshViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        return Response(identity.refresh_tokens(s.validated_data['refresh_token']))

class MobileLogoutViewPostInput(serializers.Serializer):
    all_sessions = serializers.BooleanField(default=False)

class MobileLogoutView(APIView):
    permission_classes=[IsAuthenticated]
    @extend_schema(request=MobileLogoutViewPostInput, methods=["POST"])
    def post(self,request):
        if is_device(request.user):raise PermissionDenied('Adult account required.')
        Input = MobileLogoutViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        session=request.auth if isinstance(request.auth,AdultTokenSession) else None
        if not session and not s.validated_data['all_sessions']:
            raise PermissionDenied('Bearer session required for single-session logout.')
        identity.revoke_sessions(request.user,None if s.validated_data['all_sessions'] else session)
        return Response(status=204)

class ContactChallengeViewPostInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    email = serializers.EmailField()

class ContactChallengeView(PublicIdentityView):
    @extend_schema(request=ContactChallengeViewPostInput, methods=["POST"])
    def post(self,request):
        Input = ContactChallengeViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True);d=s.validated_data
        user=authenticate(username=d['username'],password=d['password'])
        if not user:raise AuthenticationFailed('Invalid credentials.')
        identity.create_challenge(user,'contact',d['email'])
        return Response({'status':'challenge_queued','delivery':'simulated_only'},status=202)

class RecoverViewPostInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)

class RecoverView(PublicIdentityView):
    throttle_scope='recovery'
    @extend_schema(request=RecoverViewPostInput, methods=["POST"])
    def post(self,request):
        Input = RecoverViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        identity.request_recovery(s.validated_data['username'])
        return Response({'status':'If eligible, a recovery challenge has been queued.','delivery':'simulated_only'},status=202)

class CompleteChallengeViewPostInput(serializers.Serializer):
    token = serializers.CharField(min_length=20, max_length=200)
    new_password = serializers.CharField(required=False, min_length=8, max_length=128)

class CompleteChallengeView(PublicIdentityView):
    @extend_schema(request=CompleteChallengeViewPostInput, methods=["POST"])
    def post(self,request,purpose):
        Input = CompleteChallengeViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        if purpose not in ['contact','recovery']:raise PermissionDenied()
        if purpose=='recovery' and not s.validated_data.get('new_password'):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'new_password':'Required for recovery.'})
        identity.consume_challenge(s.validated_data['token'],purpose,s.validated_data.get('new_password'))
        return Response({'status':'completed'})
