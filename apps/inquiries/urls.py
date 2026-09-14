from django.urls import path
from apps.inquiries.views import (
    InquiryListCreateView,
    InquiryDetailUpdateView,
    InquiryNoteListCreateView,
)

app_name = "inquiries"

urlpatterns = [
    path("", InquiryListCreateView.as_view(), name="inquiry-list-create"),
    path("<str:inquiry_number>/", InquiryDetailUpdateView.as_view(), name="inquiry-detail"),
    path("<str:inquiry_number>/notes/", InquiryNoteListCreateView.as_view(), name="inquiry-notes"),
]
