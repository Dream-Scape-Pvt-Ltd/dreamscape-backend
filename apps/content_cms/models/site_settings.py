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
    home_caption = models.CharField(max_length=500, blank=True, default="A world above the ordinary.")
    home_location = models.CharField(max_length=500, blank=True, default="The Himalayas, Nepal")
    nepal_title = models.CharField(max_length=500, blank=True, default="Nepal")
    nepal_description = models.CharField(max_length=500, blank=True, default="High passes, quiet valleys and the places we call home.")
    nepal_image = models.CharField(max_length=500, blank=True, default="/images/trek-memories/mountain-amphitheatre.jpg")
    beyond_title = models.CharField(max_length=500, blank=True, default="Beyond Nepal")
    beyond_description = models.CharField(max_length=500, blank=True, default="Neighbouring cultures, open landscapes and new horizons.")
    beyond_image = models.CharField(max_length=500, blank=True, default="/images/dreamscape-landscape-vector.svg")
    admin_login_image = models.CharField(max_length=500, default="/images/admin-login-background.png")
    featured_video_title = models.CharField(max_length=180, default="A journey through Nepal")
    featured_video_description = models.CharField(max_length=500, default="Mountain trails, village encounters and the quiet moments that stay with you. A glimpse of journeys with Dreamscape Treks.")
    featured_video_thumbnail = models.CharField(max_length=500, default="/images/trek-memories/home-slide-3.jpg")
    home_filter_destinations = models.TextField(default="|Anywhere\nnepal|Nepal\nbeyond-nepal|Beyond Nepal")
    home_filter_difficulties = models.TextField(default="|Any difficulty\neasy|Easy\nmoderate|Moderate\nchallenging|Challenging")
    home_filter_budgets = models.TextField(default="|Any budget\nunder-1500|Under $1,500\n1500-2500|$1,500 – $2,500\nover-2500|Above $2,500")
    home_title = models.CharField(max_length=180, default='Beyond the Horizon.')
    home_description = models.CharField(max_length=500, default='Nepal treks, shaped around you. Explore the Himalaya with a team rooted here.')
    home_eyebrow = models.CharField(max_length=150, default='Local journeys · Since 2005')
    company_title = models.CharField(max_length=180, default='Rooted in Nepal.')
    company_accent = models.CharField(max_length=180, default='Built around people.')
    gallery_title = models.CharField(max_length=180, default='Nepal, in pictures.')
    gallery_description = models.CharField(max_length=500, default='Mountain light. A path through the valley. A moment shared. A few reasons to keep looking beyond the horizon.')
    company_content = models.JSONField(default=dict, blank=True)
    partner_content = models.JSONField(default=dict, blank=True)
    gallery_images = models.JSONField(default=None, null=True, blank=True)
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
