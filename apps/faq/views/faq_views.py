from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics
from rest_framework.response import Response

from apps.content_cms.views.permissions import IsAdminOrReadOnly, is_editor
from apps.faq.models import FAQ
from apps.faq.serializers.faq_serializers import FAQSerializer, FAQResponseSerializer


def public_faqs():
    return FAQ.objects.filter(is_active=True).filter(
        Q(trip__isnull=True) | Q(trip__is_active=True)
    ).filter(Q(destination__isnull=True) | Q(destination__is_active=True))


class FAQListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = FAQSerializer
    pagination_class = None
    filterset_fields = ['category']

    def get_queryset(self):
        qs = FAQ.objects.all() if is_editor(self.request.user) else public_faqs()
        qs = qs.select_related('trip', 'destination').order_by('display_order', 'id')
        for field in ['trip', 'destination']:
            slug = self.request.query_params.get(field)
            if slug:
                qs = qs.filter(**{f'{field}__slug': slug})
        return qs

    @extend_schema(responses=FAQResponseSerializer, parameters=[
        OpenApiParameter('trip', str), OpenApiParameter('destination', str)])
    def get(self, request, *args, **kwargs):
        faqs = list(self.filter_queryset(self.get_queryset()))
        return Response({'faqs': self.get_serializer(faqs, many=True).data,
                         'schema_org': {'@context': 'https://schema.org', '@type': 'FAQPage',
                                        'mainEntity': [{'@type': 'Question', 'name': faq.question,
                                                        'acceptedAnswer': {'@type': 'Answer', 'text': faq.answer}}
                                                       for faq in faqs]}})


class FAQDetailView(generics.UpdateAPIView, generics.DestroyAPIView):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.select_related('trip', 'destination')
    http_method_names = ['patch', 'delete', 'options']

    def perform_destroy(self, instance):
        FAQ.objects.filter(pk=instance.pk).update(is_active=False, updated_at=timezone.now())
