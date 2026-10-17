from rest_framework import serializers

from .models import EmailTemplate, OutboundEmail
from .rendering import VARIABLES, unknown_placeholders


def _placeholder_error(bad):
    allowed = ", ".join("{{%s}}" % name for name in VARIABLES)
    return f"Unknown placeholder(s): {', '.join('{{%s}}' % b for b in bad)}. Allowed: {allowed}."


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ["id", "slug", "name", "subject", "body_html", "body_text", "is_system", "is_active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]

    def validate(self, attrs):
        bad = unknown_placeholders(attrs.get("subject"), attrs.get("body_html"), attrs.get("body_text"))
        if bad:
            raise serializers.ValidationError(_placeholder_error(bad))
        return attrs

    def validate_slug(self, value):
        if self.instance and self.instance.is_system and value != self.instance.slug:
            raise serializers.ValidationError("The slug of a system template cannot change.")
        return value


class OutboundEmailSerializer(serializers.ModelSerializer):
    inquiry_number = serializers.CharField(source="inquiry.inquiry_number", read_only=True, default=None)
    template_name = serializers.CharField(source="template.name", read_only=True, default=None)
    sent_by_name = serializers.SerializerMethodField()

    class Meta:
        model = OutboundEmail
        fields = ["id", "recipient", "subject", "body_html", "body_text", "reply_to", "kind", "status",
                  "inquiry_number", "template_name", "sent_by_name", "attempts", "last_error",
                  "sent_at", "last_event_at", "created_at"]
        read_only_fields = fields

    def get_sent_by_name(self, obj):
        return (obj.sent_by.get_full_name() or obj.sent_by.email) if obj.sent_by else None


class SendEmailSerializer(serializers.Serializer):
    """Send a template (optionally with edited subject/message) or a hand-written email."""

    recipient = serializers.EmailField()
    template = serializers.PrimaryKeyRelatedField(
        queryset=EmailTemplate.objects.filter(is_active=True), required=False, allow_null=True
    )
    inquiry_number = serializers.CharField(required=False, allow_blank=True)
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    body_text = serializers.CharField(max_length=20000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("template") and not (attrs.get("subject") and attrs.get("body_text")):
            raise serializers.ValidationError("Choose a template, or enter a subject and message.")
        bad = unknown_placeholders(attrs.get("subject"), attrs.get("body_text"))
        if bad:
            raise serializers.ValidationError(_placeholder_error(bad))
        return attrs
