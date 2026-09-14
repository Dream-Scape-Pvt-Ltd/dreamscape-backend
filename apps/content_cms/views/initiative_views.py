from rest_framework import generics
from apps.content_cms.models import ResponsibleTravelInitiative
from apps.content_cms.serializers.initiative_serializers import ResponsibleTravelSerializer
from .permissions import IsAdminOrReadOnly, is_editor


class InitiativeQuerysetMixin:
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = ResponsibleTravelSerializer

    def get_queryset(self):
        qs = ResponsibleTravelInitiative.objects.order_by('title', 'id')
        return qs if is_editor(self.request.user) else qs.filter(is_published=True)


class ResponsibleTravelListCreateView(InitiativeQuerysetMixin, generics.ListCreateAPIView):
    pass


class ResponsibleTravelDetailView(InitiativeQuerysetMixin, generics.RetrieveAPIView):
    lookup_field = 'slug'
