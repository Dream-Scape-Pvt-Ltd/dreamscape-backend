from .inquiry_serializers import (
    InquiryCreateSerializer,
    InquiryDetailSerializer,
    InquiryListSerializer,
    InquiryNoteSerializer,
    InquiryUpdateSerializer,
)
from .tailor_made_serializers import (
    TailorMadeRequestSerializer,
    TailorMadeRequestCreateSerializer,
)
from .activity_serializers import ActivitySerializer, ActivityCreateSerializer
from .task_serializers import TaskSerializer, TaskCreateSerializer, TaskUpdateSerializer
from .tag_serializers import TagSerializer
from .customer_serializers import CustomerSerializer
from .revenue_serializers import RevenueEntrySerializer

__all__ = [
    "InquiryCreateSerializer",
    "InquiryDetailSerializer",
    "InquiryListSerializer",
    "InquiryNoteSerializer",
    "InquiryUpdateSerializer",
    "TailorMadeRequestSerializer",
    "TailorMadeRequestCreateSerializer",
    "ActivitySerializer",
    "ActivityCreateSerializer",
    "TaskSerializer",
    "TaskCreateSerializer",
    "TaskUpdateSerializer",
    "TagSerializer",
    "CustomerSerializer",
    "RevenueEntrySerializer",
]
