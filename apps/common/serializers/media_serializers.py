from rest_framework import serializers
from apps.common.models.media import MediaAsset

class MediaAssetReadSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MediaAsset
        fields = [
            "id",
            "file",
            "original_name",
            "mime_type",
            "file_size_bytes",
            "alt_text",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
            "updated_at",
        ]

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name()

class MediaAssetWriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = MediaAsset
        fields = [
            "file",
            "original_name",
            "mime_type",
            "file_size_bytes",
            "alt_text",
        ]

    def create(self, validated_data):
        request = self.context.get("request")

        validated_data["uploaded_by"] = request.user

        return MediaAsset.objects.create(**validated_data)