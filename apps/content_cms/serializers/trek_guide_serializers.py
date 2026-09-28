from urllib.parse import urlsplit
from rest_framework import serializers
from apps.content_cms.models import TrekGuide
from apps.destinations.models import Destination
from apps.trips.models import Trip

class GuideRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ['id','name','slug']

class GuideTripSerializer(serializers.ModelSerializer):
    destination_name = serializers.CharField(source='destination.name')
    destination_slug = serializers.CharField(source='destination.slug')
    category_name = serializers.CharField(source='category.name')
    category_slug = serializers.CharField(source='category.slug')
    class Meta:
        model = Trip
        fields = ['id','slug','title','destination_id','destination_name','destination_slug','category_name','category_slug','duration_days','starting_price_usd','altitude_max_meters','difficulty_grade','hero_image_url']

class TrekGuideReadSerializer(serializers.ModelSerializer):
    regions = GuideRegionSerializer(many=True)
    treks_led = GuideTripSerializer(many=True)
    class Meta:
        model = TrekGuide
        fields = ['id','slug','name','role','photo_url','bio','years_experience','languages','certifications','regions','treks_led','is_published','display_order']

class TrekGuideWriteSerializer(serializers.ModelSerializer):
    regions = serializers.SlugRelatedField(slug_field='slug',queryset=Destination.objects.all(),many=True,required=False)
    treks_led = serializers.SlugRelatedField(slug_field='slug',queryset=Trip.objects.all(),many=True,required=False)
    languages = serializers.ListField(child=serializers.CharField(max_length=120),max_length=30,required=False)
    certifications = serializers.ListField(child=serializers.CharField(max_length=200),max_length=30,required=False)
    class Meta:
        model = TrekGuide
        fields = ['slug','name','role','photo_url','bio','years_experience','languages','certifications','regions','treks_led','is_published','display_order']
    def validate_photo_url(self,value):
        if not value:return value
        url=urlsplit(value)
        if not value.startswith(('/images/','/media/')) and not (url.scheme in ['https','http'] and url.netloc and not url.username and not url.password):
            raise serializers.ValidationError('Use an http(s) photo URL or an /images/ or /media/ path.')
        return value
