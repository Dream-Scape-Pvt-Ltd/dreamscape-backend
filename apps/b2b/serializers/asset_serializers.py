from rest_framework import serializers
from apps.b2b.models import B2BAsset, AgencyTier

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

    class Meta:
        model = B2BAsset
        fields = [
            "id",
            "trip",
            "trip_title",
            "title",
            "asset_type",
            "file",
            "minimum_tier",
            "is_accessible",
            "created_at",
        ]
        read_only_fields = fields

    def get_is_accessible(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        partner = getattr(request.user, "b2b_profile", None)
        if not partner or not partner.approved:
            return False

        partner_rank = TIER_RANKS.get(partner.agency_tier, 0)
        asset_rank = TIER_RANKS.get(obj.minimum_tier, 1)
        return partner_rank >= asset_rank
