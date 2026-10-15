from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from common.audit import audit
from families.models import Household, Guardian

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, max_length=128)
    household_name = serializers.CharField(max_length=120, write_only=True)
    class Meta:
        model = get_user_model()
        fields = ['username','password','household_name']
    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

@method_decorator(csrf_protect, name='dispatch')
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = get_user_model().objects.create_user(username=data['username'], password=data['password'])
        household = Household.objects.create(name=data['household_name'])
        Guardian.objects.create(user=user, household=household)
        audit(user, 'household.registered', household)
        # Registration does not grant subscription or assert legal authority.
        return Response({'household': household.id}, status=201)

@method_decorator(csrf_protect, name='dispatch')
class SessionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        from django.middleware.csrf import get_token
        return Response({'csrf_token': get_token(request), 'authentication': 'session'})
    def post(self, request):
        class Input(serializers.Serializer):
            username = serializers.CharField(max_length=150)
            password = serializers.CharField(max_length=128)
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request=request, **serializer.validated_data)
        if not user:
            raise ValidationError('Invalid credentials.')
        login(request, user)
        from django.middleware.csrf import get_token
        return Response({'authenticated': True, 'csrf_token': get_token(request)})
    def delete(self, request):
        logout(request)
        return Response(status=204)

class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        return Response({'status': 'ok', 'mode': 'foundation-simulated-providers', 'live_emergency_service': False})
