from rest_framework import serializers
from apps.faq.models import FAQ


class FAQSerializer(serializers.ModelSerializer):
    """
    Contextual FAQ accordion serializer.
    ORM Dependencies: select_related('trip', 'destination')
    Provides single-item or collection Schema.org Question/Answer JSON-LD structure.
    """

    trip_title = serializers.CharField(source="trip.title", read_only=True, allow_null=True)
    destination_name = serializers.CharField(source="destination.name", read_only=True, allow_null=True)
    schema_org_json_ld = serializers.SerializerMethodField()

    class Meta:
        model = FAQ
        fields = [
            "id",
            "trip",
            "trip_title",
            "destination",
            "destination_name",
            "question",
            "answer",
            "category",
            "display_order",
            "schema_org_json_ld",
            "is_active",
        ]
        read_only_fields = ['id', 'trip_title', 'destination_name', 'schema_org_json_ld']

    def get_schema_org_json_ld(self, obj) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "Question",
            "name": obj.question,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": obj.answer,
            },
        }


class FAQResponseSerializer(serializers.Serializer):
    faqs = FAQSerializer(many=True)
    schema_org = serializers.JSONField()
