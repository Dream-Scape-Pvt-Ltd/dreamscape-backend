from django.db import models


class SiteSettings(models.Model):
    """One editable public website record; never store private keys here."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    city = models.CharField(max_length=150, default="Kathmandu, Nepal")
    area = models.CharField(max_length=100, default="Thamel")
    address = models.CharField(max_length=300, default="Below Hotel Avalon, Thamel, Kathmandu, Nepal")
    map_query = models.CharField(max_length=300, default="Avalon House, Lekhnath Marg, Thamel, Kathmandu, Nepal")
    directions_note = models.CharField(max_length=500, blank=True, default="The map marks the Hotel Avalon landmark. Get in touch for help finding the entrance.")
    map_zoom = models.PositiveSmallIntegerField(default=16)
    journal_title = models.CharField(max_length=120, default="Stories worth taking the long way for.")
    journal_description = models.CharField(max_length=400, default="Walk a little further into Nepal. Meet the people, discover the places, and find inspiration for a journey of your own.")
    featured_story_slug = models.SlugField(max_length=255, blank=True)
    home_image_url = models.URLField(max_length=500, blank=True)
    home_image_alt = models.CharField(max_length=250, default="Trekkers beneath Himalayan snow peaks")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "site_settings"
        verbose_name_plural = "Website settings"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="site_settings_singleton")]

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Dreamscape website"
