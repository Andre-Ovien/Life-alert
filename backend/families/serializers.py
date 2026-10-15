from rest_framework import serializers
from .models import Household, Child, Device, EmergencyContact, CareMedia

class HouseholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Household
        fields = ['id', 'name']
        read_only_fields = ['id']

class ChildSerializer(serializers.ModelSerializer):
    expected_version = serializers.IntegerField(required=False, write_only=True, min_value=0)
    class Meta:
        model = Child
        fields = ['id', 'household', 'name', 'communication', 'support_needs', 'calming_preferences', 'saved_address', 'current_version', 'updated_at', 'updated_by', 'expected_version']
        read_only_fields = ['id','current_version','updated_at','updated_by']

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'child', 'label', 'expires_at', 'revoked_at','rotated_from']
        read_only_fields = ['id', 'expires_at','revoked_at','rotated_from']

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = ['id', 'child', 'name', 'phone', 'relationship', 'active']
        read_only_fields = ['id']

class MediaSerializer(serializers.ModelSerializer):
    # No raw storage URL or filename exposed.
    has_audio = serializers.SerializerMethodField()
    def get_has_audio(self, obj) -> bool:
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

class SavedPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import SavedPlace
        model = SavedPlace
        fields = ['id','child','label','address','is_default','active']
        read_only_fields = ['id']

class GrantSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import CaregiverGrant
        model = CaregiverGrant
        fields = ['id','child','user','relationship','can_view_care','can_view_incidents',
            'can_request_help','can_manage_profile','can_manage_media','can_manage_devices','expires_at','revoked_at']
        read_only_fields = fields

class InvitationSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.ChoiceField(choices=['view_care','view_incidents','request_help','manage_profile','manage_media','manage_devices']))
    class Meta:
        from .models import CaregiverInvitation
        model = CaregiverInvitation
        fields = ['id','child','recipient','relationship','permissions','expires_at','status']
        read_only_fields = ['id','expires_at','status']
