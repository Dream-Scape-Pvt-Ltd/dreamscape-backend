from rest_framework import serializers
from apps.b2b.models import B2BAsset, AgencyTier
from django.urls import reverse
from apps.accounts.models import UserRole

TIER_RANKS = {
    AgencyTier.BRONZE: 1,
    AgencyTier.SILVER: 2,
    AgencyTier.GOLD: 3,
    AgencyTier.PLATINUM: 4,
}


class B2BAssetSerializer(serializers.ModelSerializer):
    """
    Marketing download assets serializer.
    ORM Dependencies: select_related('trip')
    Can check if the requesting partner tier meets the minimum tier requirement.
    """

    trip_title = serializers.CharField(source="trip.title", read_only=True)
    is_accessible = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = B2BAsset
        fields = [
            "id",
            "trip",
            "trip_title",
            "title",
            "asset_type",
            "download_url",
            "minimum_tier",
            "is_accessible",
            "created_at",
        ]
        read_only_fields = fields

    def get_is_accessible(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if request.user.role == UserRole.ADMIN:
            return True
        partner = getattr(request.user, "b2b_profile", None)
        if not partner or not partner.approved:
            return False

        partner_rank = TIER_RANKS.get(partner.agency_tier, 0)
        asset_rank = TIER_RANKS.get(obj.minimum_tier, 1)
        return partner_rank >= asset_rank

    def get_download_url(self, obj) -> str | None:
        if not self.get_is_accessible(obj):
            return None
        return reverse('b2b:asset-download', kwargs={'asset_id': obj.pk})


class B2BAssetDownloadSerializer(serializers.Serializer):
    download_url = serializers.CharField()
    expires_in_seconds = serializers.IntegerField()
