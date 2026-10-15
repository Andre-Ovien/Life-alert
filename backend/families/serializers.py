from rest_framework import serializers
from .models import Household, Child, Device, EmergencyContact, CareMedia

class HouseholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Household
        fields = ['id', 'name']
        read_only_fields = ['id']

class ChildSerializer(serializers.ModelSerializer):
    class Meta:
        model = Child
        fields = ['id', 'household', 'name', 'communication', 'support_needs', 'calming_preferences', 'saved_address']
        read_only_fields = ['id']

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'child', 'label', 'revoked_at']
        read_only_fields = ['id', 'revoked_at']

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = ['id', 'child', 'name', 'phone', 'relationship']
        read_only_fields = ['id']

class MediaSerializer(serializers.ModelSerializer):
    # No raw storage URL or filename exposed.
    has_audio = serializers.SerializerMethodField()
    def get_has_audio(self, obj):
        return bool(obj.file)
    def validate(self, attrs):
        child_audience = attrs.get('for_child', getattr(self.instance, 'for_child', False))
        responder_audience = attrs.get('for_responder', getattr(self.instance, 'for_responder', False))
        if not (child_audience or responder_audience):
            raise serializers.ValidationError('At least one audience is required.')
        return attrs
    class Meta:
        model = CareMedia
        fields = ['id', 'child', 'title', 'for_child', 'for_responder', 'instructions_text', 'has_audio']
        read_only_fields = ['id', 'has_audio']
