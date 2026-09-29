import uuid

from django.db import models

from apps.common.models.base import TimeStampedModel

SITE_SETTINGS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class SiteSettings(TimeStampedModel):
    """
    The single row of settings editors manage in admin → Settings.

    `content` is public website copy, header menus and contact details, stored as
    one JSON object that the frontend merges over its own defaults.
    `crm_sla_hours` is internal: hours before an unanswered inquiry is flagged
    overdue. Empty means the CRM_SLA_HOURS server setting applies.
    """

    content = models.JSONField(default=dict, blank=True)
    crm_sla_hours = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "site_settings"
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def save(self, *args, **kwargs):
        self.pk = SITE_SETTINGS_ID
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Site settings cannot be deleted.")

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=SITE_SETTINGS_ID)[0]

    def __str__(self):
        return "Site settings"
