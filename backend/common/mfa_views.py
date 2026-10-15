from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import serializers
from rest_framework.response import Response
from . import mfa
from .models import StaffMFA

class MFAViewPostInput(serializers.Serializer):
    password = serializers.CharField(max_length=128, required=False)
    code = serializers.CharField(max_length=100, required=False)

class MFAView(APIView):
    http_method_names=["post", "options"]
    permission_classes=[IsAuthenticated]
    throttle_classes=[ScopedRateThrottle]
    throttle_scope='identity'
    @extend_schema(request=MFAViewPostInput, methods=["POST"])
    def post(self,request,operation):
        Input = MFAViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True);d=s.validated_data
        from rest_framework.exceptions import ValidationError
        if operation in ['enroll','disable'] and 'password' not in d:raise ValidationError({'password':'Required.'})
        if operation in ['confirm','verify','disable'] and 'code' not in d:raise ValidationError({'code':'Required.'})
        if operation=='enroll':return Response(mfa.enroll(request.user,d['password']),status=201)
        if operation in ['confirm','verify']:return Response(mfa.verify(request,d['code'],confirm=operation=='confirm'))
        if operation=='disable':
            mfa.disable(request.user,d['password'],d['code'])
            return Response(status=204)
        raise ValidationError('Unknown MFA operation.')

class MFAStatusView(MFAView):
    http_method_names=["get", "head", "options"]
    def get(self,request):
        mfa.adult(request.user)
        return Response({'enrolled':StaffMFA.objects.filter(user=request.user,confirmed_at__isnull=False).exists()})
