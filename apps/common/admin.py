from django.contrib import admin
from apps.common .models import MediaAsset, NotificationLog, AuditLog


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "original_name", "mime_type", "file_size_bytes", "uploaded_by", "created_at")
    search_fields = ("original_name", "alt_text", "uploaded_by__email")
    list_filter = ("mime_type", "created_at")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "recipient", "event_type", "status", "created_at")
    search_fields = ("recipient", "subject", "provider_message_id")
    list_filter = ("channel", "status", "event_type", "created_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "actor", "action", "entity_type", "entity_id", "created_at")
    search_fields = ("action", "entity_type", "entity_id", "actor__email")
    list_filter = ("action", "entity_type", "created_at")


from apps.common.models import TransactionalEmail

@admin.register(TransactionalEmail)
class TransactionalEmailAdmin(admin.ModelAdmin):
    list_display = ('event_key','recipient','sent_at','attempts','needs_review','next_attempt_at')
    list_filter = ('needs_review','sent_at')
    readonly_fields = ('event_key','recipient','subject','body','sent_at','first_attempt_at','next_attempt_at','attempts','provider_message_id')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
