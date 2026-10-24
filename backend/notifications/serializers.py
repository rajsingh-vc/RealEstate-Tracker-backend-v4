from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    actor_username = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'verb', 'description', 'target_url', 'is_read', 'created_at',
            'actor', 'actor_name', 'actor_username',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if not obj.actor_id:
            return None
        return obj.actor.name or obj.actor.username

    def get_actor_username(self, obj):
        if not obj.actor_id:
            return None
        return obj.actor.username
