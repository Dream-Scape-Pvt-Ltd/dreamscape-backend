from .inquiry_views import (
    InquiryListCreateView,
    InquiryDetailUpdateView,
    InquiryNoteListCreateView,
)
from .activity_views import InquiryTimelineView, ActivityListCreateView
from .task_views import TaskListCreateView, MyTasksView, TaskDetailUpdateView
from .tag_views import TagListCreateView, InquiryTagView
from .customer_views import CustomerDetailView
from .crm_analytics_views import PipelineSummaryView, FunnelView, TrekPipelineView
from .revenue_views import RevenueAnalyticsView, RevenueEntryDetailView, RevenueEntryListCreateView
from .assignment_views import (
    BulkAssignView,
    LeadAssignmentRuleDetailView,
    LeadAssignmentRuleListCreateView,
    LeadsByDepartureView,
)

__all__ = [
    "InquiryListCreateView",
    "InquiryDetailUpdateView",
    "InquiryNoteListCreateView",
    "InquiryTimelineView",
    "ActivityListCreateView",
    "TaskListCreateView",
    "MyTasksView",
    "TaskDetailUpdateView",
    "TagListCreateView",
    "InquiryTagView",
    "CustomerDetailView",
    "PipelineSummaryView",
    "TrekPipelineView",
    "FunnelView",
    "BulkAssignView",
    "LeadAssignmentRuleListCreateView",
    "LeadAssignmentRuleDetailView",
    "LeadsByDepartureView",
    "RevenueAnalyticsView",
    "RevenueEntryListCreateView",
    "RevenueEntryDetailView",
]
