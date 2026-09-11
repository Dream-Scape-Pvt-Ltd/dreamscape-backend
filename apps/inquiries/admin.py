from django.contrib import admin
from apps.inquiries.models import Inquiry, TailorMadeRequest, InquiryNote


class TailorMadeRequestInline(admin.StackedInline):
    model = TailorMadeRequest
    can_delete = False
    max_num = 1


class InquiryNoteInline(admin.TabularInline):
    model = InquiryNote
    extra = 1
    fields = ("author", "note_text", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = (
        "inquiry_number",
        "full_name",
        "email",
        "inquiry_type",
        "status",
        "trip",
        "assigned_agent",
        "created_at",
    )
    list_filter = ("status", "inquiry_type", "lead_source", "created_at")
    search_fields = ("inquiry_number", "full_name", "email", "phone")
    readonly_fields = ("inquiry_number", "created_at", "updated_at")
    inlines = [TailorMadeRequestInline, InquiryNoteInline]


@admin.register(InquiryNote)
class InquiryNoteAdmin(admin.ModelAdmin):
    list_display = ("inquiry", "author", "created_at")
    search_fields = ("inquiry__inquiry_number", "author__email", "note_text")
