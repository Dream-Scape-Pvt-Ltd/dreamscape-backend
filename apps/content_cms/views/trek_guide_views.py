from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics,status
from rest_framework.response import Response
from apps.content_cms.models import TrekGuide
from apps.content_cms.serializers.trek_guide_serializers import TrekGuideReadSerializer,TrekGuideWriteSerializer
from apps.trips.models import Trip
from apps.trips.lookup import trip_lookup
from .permissions import IsAdminOrReadOnly,is_editor

class GuideProfilesMixin:
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = TrekGuideReadSerializer
    def get_queryset(self):
        editor = is_editor(self.request.user)
        trips = Trip.objects.select_related('destination','category')
        if not editor:trips=trips.filter(is_active=True)
        qs = TrekGuide.objects.prefetch_related('regions',Prefetch('treks_led',queryset=trips))
        return qs if editor else qs.filter(is_published=True)

class TrekGuideListCreateView(GuideProfilesMixin,generics.ListCreateAPIView):
    @transaction.atomic
    def post(self,request,*args,**kwargs):
        serializer=TrekGuideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guide=serializer.save()
        return Response(TrekGuideReadSerializer(self.get_queryset().get(pk=guide.pk)).data,status=status.HTTP_201_CREATED)

class TrekGuideDetailView(GuideProfilesMixin,generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ['get','patch','delete','head','options']
    def get_object(self):
        obj=get_object_or_404(self.get_queryset(),**trip_lookup(self.kwargs['slug']))
        self.check_object_permissions(self.request,obj)
        return obj
    @transaction.atomic
    def patch(self,request,*args,**kwargs):
        guide=TrekGuide.objects.select_for_update().get(pk=self.get_object().pk)
        serializer=TrekGuideWriteSerializer(guide,data=request.data,partial=True)
        serializer.is_valid(raise_exception=True)
        guide=serializer.save()
        return Response(TrekGuideReadSerializer(self.get_queryset().get(pk=guide.pk)).data)
    @transaction.atomic
    def delete(self,request,*args,**kwargs):
        guide=self.get_object()
        if request.query_params.get('permanent')=='true':guide.delete()
        else:guide.is_published=False;guide.save(update_fields=['is_published','updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)
