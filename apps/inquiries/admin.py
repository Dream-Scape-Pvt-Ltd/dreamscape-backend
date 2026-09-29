from django.contrib import admin
from apps.inquiries.models import (
    Activity,
    Customer,
    Inquiry,
    InquiryNote,
    LeadAssignmentRule,
    Tag,
    TailorMadeRequest,
    Task,
)


@admin.register(LeadAssignmentRule)
class LeadAssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ("target_label", "agent", "priority", "is_active", "created_at")
    list_filter = ("is_active", "agent")
    search_fields = ("trip__title", "destination__name", "agent__email")
    autocomplete_fields = ("agent",)


class TailorMadeRequestInline(admin.StackedInline):
    model = TailorMadeRequest
    can_delete = False
    max_num = 1


class InquiryNoteInline(admin.TabularInline):
    model = InquiryNote
    extra = 1
    fields = ("author", "note_text", "created_at")
    readonly_fields = ("created_at",)


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ("channel", "author", "body", "created_at")
    readonly_fields = ("created_at",)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("title", "assigned_agent", "due_at", "status")


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
        "sla_breached",
        "created_at",
    )
    list_filter = ("status", "inquiry_type", "trip_style", "lead_source", "sla_breached", "tags", "created_at")
    search_fields = ("inquiry_number", "full_name", "email", "phone")
    readonly_fields = ("inquiry_number", "created_at", "updated_at")
    autocomplete_fields = ("customer", "converted_booking")
    filter_horizontal = ("tags",)
    inlines = [TailorMadeRequestInline, InquiryNoteInline, ActivityInline, TaskInline]


@admin.register(InquiryNote)
class InquiryNoteAdmin(admin.ModelAdmin):
    list_display = ("inquiry", "author", "created_at")
    search_fields = ("inquiry__inquiry_number", "author__email", "note_text")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "phone", "lifetime_inquiries", "lifetime_bookings", "lifetime_value_usd")
    search_fields = ("email", "full_name", "phone")
    readonly_fields = ("lifetime_inquiries", "lifetime_bookings", "lifetime_value_usd", "created_at", "updated_at")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("inquiry", "channel", "author", "created_at")
    list_filter = ("channel", "created_at")
    search_fields = ("inquiry__inquiry_number", "body")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "inquiry", "assigned_agent", "due_at", "status")
    list_filter = ("status", "due_at")
    search_fields = ("title", "inquiry__inquiry_number")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)
