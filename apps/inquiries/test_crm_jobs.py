"""
CRM background sweeps (SLA breaches, task reminders, customer rollup) and the
agent-facing task, activity, timeline, and tag endpoints that sit around them.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.bookings.models import Booking
from apps.inquiries import tasks as crm_tasks
from apps.inquiries.models import (
    Activity,
    ActivityChannel,
    Customer,
    Inquiry,
    InquiryNote,
    InquiryStatus,
    InquiryType,
    LeadAssignmentRule,
    Tag,
    Task,
    TaskStatus,
)
from apps.inquiries.test_assignment import CRMTestBase


class CRMJobTestBase(CRMTestBase):
    _counter = 0

    def make_lead(self, age_hours=0, **extra):
        CRMJobTestBase._counter += 1
        number = f"INQ-2026-9{CRMJobTestBase._counter:03d}"
        defaults = {
            "inquiry_number": number,
            "inquiry_type": InquiryType.GENERAL,
            "full_name": "Lhakpa Dorje",
            "email": f"{number.lower()}@test.local",
            "status": InquiryStatus.NEW,
        }
        defaults.update(extra)
        inquiry = Inquiry.objects.create(**defaults)
        if age_hours:
            # created_at is auto_now_add, so backdate it with a queryset update.
            Inquiry.objects.filter(pk=inquiry.pk).update(created_at=timezone.now() - timedelta(hours=age_hours))
            inquiry.refresh_from_db()
        return inquiry

    def make_task(self, inquiry, due_in, **extra):
        defaults = {
            "inquiry": inquiry,
            "assigned_agent": self.annapurna_agent,
            "title": "Call back about dates",
            "due_at": timezone.now() + due_in,
        }
        defaults.update(extra)
        return Task.objects.create(**defaults)


@override_settings(CRM_SLA_HOURS=4)
class SLABreachSweepTests(CRMJobTestBase):
    @mock.patch.object(crm_tasks, "send_sla_breach_alert")
    def test_stale_unanswered_lead_is_flagged_once(self, alert):
        stale = self.make_lead(age_hours=5)

        self.assertEqual(crm_tasks.check_sla_breaches(), 1)
        stale.refresh_from_db()
        self.assertTrue(stale.sla_breached)
        alert.assert_called_once_with(stale.id)

        # A second sweep must not re-alert the manager.
        self.assertEqual(crm_tasks.check_sla_breaches(), 0)
        self.assertEqual(alert.call_count, 1)

    @mock.patch.object(crm_tasks, "send_sla_breach_alert")
    def test_fresh_answered_or_progressed_leads_are_left_alone(self, alert):
        fresh = self.make_lead(age_hours=1)
        answered = self.make_lead(age_hours=10, first_response_at=timezone.now())
        progressed = self.make_lead(age_hours=10, status=InquiryStatus.IN_CONTACT)

        self.assertEqual(crm_tasks.check_sla_breaches(), 0)
        alert.assert_not_called()
        for lead in (fresh, answered, progressed):
            lead.refresh_from_db()
            self.assertFalse(lead.sla_breached)

    @override_settings(CRM_SLA_HOURS=24)
    @mock.patch.object(crm_tasks, "send_sla_breach_alert")
    def test_sla_window_comes_from_settings(self, alert):
        self.make_lead(age_hours=5)
        self.assertEqual(crm_tasks.check_sla_breaches(), 0)

    @override_settings(CRM_SLA_HOURS=24)
    @mock.patch.object(crm_tasks, "send_sla_breach_alert")
    def test_hours_set_in_admin_settings_win_over_the_server_setting(self, alert):
        from apps.content_cms.models import SiteSettings
        row = SiteSettings.load()
        row.crm_sla_hours = 2
        row.save()
        self.make_lead(age_hours=3)
        self.assertEqual(crm_tasks.check_sla_breaches(), 1)


class TaskReminderSweepTests(CRMJobTestBase):
    @mock.patch.object(crm_tasks, "send_task_reminder_alert")
    def test_open_task_due_within_the_hour_is_reminded_once(self, alert):
        lead = self.make_lead()
        due_soon = self.make_task(lead, timedelta(minutes=30))
        overdue = self.make_task(lead, -timedelta(hours=2))

        self.assertEqual(crm_tasks.send_task_reminders(), 2)
        for task in (due_soon, overdue):
            task.refresh_from_db()
            self.assertIsNotNone(task.reminder_sent_at)
        self.assertEqual(alert.call_count, 2)

        self.assertEqual(crm_tasks.send_task_reminders(), 0)
        self.assertEqual(alert.call_count, 2)

    @mock.patch.object(crm_tasks, "send_task_reminder_alert")
    def test_later_done_cancelled_and_reminded_tasks_are_skipped(self, alert):
        lead = self.make_lead()
        later = self.make_task(lead, timedelta(hours=3))
        self.make_task(lead, timedelta(minutes=10), status=TaskStatus.DONE)
        self.make_task(lead, timedelta(minutes=10), status=TaskStatus.CANCELLED)
        self.make_task(lead, timedelta(minutes=10), reminder_sent_at=timezone.now())

        self.assertEqual(crm_tasks.send_task_reminders(), 0)
        alert.assert_not_called()
        later.refresh_from_db()
        self.assertIsNone(later.reminder_sent_at)


class NightlyCustomerRollupTests(CRMJobTestBase):
    def make_booking(self, email, paid, reference):
        return Booking.objects.create(
            booking_reference=reference,
            customer_name="Repeat Traveller",
            customer_email=email,
            departure=self.march_departure,
            num_travelers=1,
            total_amount_usd=Decimal("1500.00"),
            deposit_amount_usd=Decimal("300.00"),
            balance_amount_usd=Decimal("1200.00"),
            amount_paid_usd=Decimal(paid),
            trip_start_date=self.start_date,
        )

    def test_drifted_counters_are_reconciled_from_source_rows(self):
        customer = Customer.objects.create(
            email="repeat@example.com",
            lifetime_inquiries=9,
            lifetime_bookings=9,
            lifetime_value_usd=Decimal("99999.00"),
        )
        self.make_lead(customer=customer, email=customer.email)
        self.make_lead(customer=customer, email=customer.email)
        # Booking emails are matched case-insensitively.
        self.make_booking("Repeat@Example.com", "300.00", "DS-2026-ROLL1")
        self.make_booking("repeat@example.com", "1500.00", "DS-2026-ROLL2")
        self.make_booking("someone-else@example.com", "700.00", "DS-2026-ROLL3")

        self.assertEqual(crm_tasks.nightly_customer_rollup(), 1)
        customer.refresh_from_db()
        self.assertEqual(customer.lifetime_inquiries, 2)
        self.assertEqual(customer.lifetime_bookings, 2)
        self.assertEqual(customer.lifetime_value_usd, Decimal("1800.00"))

    def test_customers_already_in_sync_are_not_rewritten(self):
        customer = Customer.objects.create(email="steady@example.com", lifetime_inquiries=1)
        self.make_lead(customer=customer, email=customer.email)

        self.assertEqual(crm_tasks.nightly_customer_rollup(), 0)


class TaskEndpointTests(CRMJobTestBase):
    def setUp(self):
        super().setUp()
        self.lead = self.make_lead(status=InquiryStatus.ASSIGNED, assigned_agent=self.annapurna_agent)
        self.client.force_authenticate(self.annapurna_agent)

    def detail_url(self, task):
        return reverse("inquiries:task-detail", kwargs={"pk": task.id})

    def test_task_can_be_assigned_to_another_agent(self):
        url = reverse("inquiries:inquiry-tasks", kwargs={"inquiry_number": self.lead.inquiry_number})
        res = self.client.post(url, {
            "title": "Hand over permit paperwork",
            "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "assigned_agent_id": str(self.other_agent.id),
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.get(inquiry=self.lead).assigned_agent, self.other_agent)

    def test_reopening_a_done_task_clears_completed_at(self):
        task = self.make_task(self.lead, timedelta(days=1))
        self.client.patch(self.detail_url(task), {"status": "DONE"}, format="json")
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)

        res = self.client.patch(self.detail_url(task), {"status": "OPEN"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.OPEN)
        self.assertIsNone(task.completed_at)

    def test_patch_answers_with_the_full_task(self):
        """The dashboard swaps the saved task into its list, so it needs the id back."""
        task = self.make_task(self.lead, timedelta(days=1))
        data = self.client.patch(self.detail_url(task), {"status": "DONE"}, format="json").json()["data"]
        self.assertEqual(data["id"], str(task.id))
        self.assertEqual(data["status"], TaskStatus.DONE)
        self.assertIsNotNone(data["completed_at"])

    def test_cancelling_does_not_stamp_completed_at(self):
        task = self.make_task(self.lead, timedelta(days=1))
        self.client.patch(self.detail_url(task), {"status": "CANCELLED"}, format="json")
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertIsNone(task.completed_at)

    def test_invalid_status_is_rejected(self):
        task = self.make_task(self.lead, timedelta(days=1))
        res = self.client.patch(self.detail_url(task), {"status": "SNOOZED"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_task_can_be_deleted(self):
        task = self.make_task(self.lead, timedelta(days=1))
        res = self.client.delete(self.detail_url(task))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_my_tasks_is_soonest_first_and_filterable_by_status(self):
        later = self.make_task(self.lead, timedelta(days=3), title="later")
        sooner = self.make_task(self.lead, timedelta(days=1), title="sooner")
        done = self.make_task(self.lead, timedelta(days=2), title="done", status=TaskStatus.DONE)

        res = self.client.get(reverse("inquiries:my-tasks"))
        ids = [row["id"] for row in res.json()["data"]["results"]]
        self.assertEqual(ids, [str(sooner.id), str(later.id)])

        res_done = self.client.get(reverse("inquiries:my-tasks"), {"status": "done"})
        self.assertEqual([row["id"] for row in res_done.json()["data"]["results"]], [str(done.id)])

    def test_any_agent_can_currently_edit_another_agents_task(self):
        """
        Documents current behaviour: task detail has no ownership check. If
        tasks become owner-only, flip this assertion to 403/404.
        """
        task = self.make_task(self.lead, timedelta(days=1))
        self.client.force_authenticate(self.other_agent)
        res = self.client.patch(self.detail_url(task), {"status": "DONE"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class ActivityAndTimelineTests(CRMJobTestBase):
    def setUp(self):
        super().setUp()
        self.lead = self.make_lead()
        self.client.force_authenticate(self.annapurna_agent)
        self.activities_url = reverse("inquiries:inquiry-activities", kwargs={"inquiry_number": self.lead.inquiry_number})
        self.timeline_url = reverse("inquiries:inquiry-timeline", kwargs={"inquiry_number": self.lead.inquiry_number})

    def log(self, channel, body="Touched base"):
        return self.client.post(self.activities_url, {"channel": channel, "body": body}, format="json")

    def test_every_manual_channel_can_be_logged(self):
        for channel in (ActivityChannel.CALL, ActivityChannel.EMAIL, ActivityChannel.WHATSAPP, ActivityChannel.NOTE, ActivityChannel.SYSTEM):
            with self.subTest(channel=channel):
                self.assertEqual(self.log(channel).status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.filter(inquiry=self.lead, author=self.annapurna_agent).count(), 5)

    def test_status_change_cannot_be_logged_by_hand(self):
        self.assertEqual(self.log(ActivityChannel.STATUS_CHANGE).status_code, status.HTTP_400_BAD_REQUEST)

    def test_internal_note_does_not_count_as_first_response(self):
        self.log(ActivityChannel.NOTE)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.first_response_at)

    def test_first_response_is_not_overwritten_by_later_outreach(self):
        self.log(ActivityChannel.CALL)
        self.lead.refresh_from_db()
        first = self.lead.first_response_at
        self.log(ActivityChannel.EMAIL)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.first_response_at, first)

    def test_timeline_merges_notes_and_activities_newest_first(self):
        self.log(ActivityChannel.CALL, "first call")
        InquiryNote.objects.create(inquiry=self.lead, author=self.annapurna_agent, note_text="a note")
        self.log(ActivityChannel.EMAIL, "follow-up email")

        res = self.client.get(self.timeline_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        entries = res.json()["data"]
        self.assertEqual([e["entry_type"] for e in entries], ["activity", "note", "activity"])
        stamps = [e["created_at"] for e in entries]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_unknown_inquiry_returns_404(self):
        url = reverse("inquiries:inquiry-timeline", kwargs={"inquiry_number": "INQ-0000-0000"})
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)


class TagEndpointTests(CRMJobTestBase):
    def setUp(self):
        super().setUp()
        self.lead = self.make_lead()
        self.tag = Tag.objects.create(name="ebc-interest")
        self.client.force_authenticate(self.annapurna_agent)
        self.attach_url = reverse("inquiries:inquiry-tags", kwargs={"inquiry_number": self.lead.inquiry_number})

    def test_duplicate_tag_names_are_rejected(self):
        res = self.client.post(reverse("inquiries:tag-list-create"), {"name": "ebc-interest"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attaching_twice_is_idempotent(self):
        self.client.post(self.attach_url, {"tag_id": str(self.tag.id)}, format="json")
        res = self.client.post(self.attach_url, {"tag_id": str(self.tag.id)}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self.lead.tags.count(), 1)

    def test_attaching_an_unknown_tag_returns_404(self):
        res = self.client.post(self.attach_url, {"tag_id": "00000000-0000-0000-0000-000000000000"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_detaching_a_tag_that_is_not_attached_is_a_no_op(self):
        url = reverse("inquiries:inquiry-tag-detail", kwargs={"inquiry_number": self.lead.inquiry_number, "tag_id": str(self.tag.id)})
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["data"], [])


class TravellerMessageTests(CRMJobTestBase):
    """The API envelope has its own "message"; it must not swallow the lead's."""

    def test_staff_see_the_travellers_message_on_detail_and_after_updates(self):
        res = self.submit_inquiry(message="We would love to trek in the spring.")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        number = res.json()["data"]["inquiry_number"]
        url = reverse("inquiries:inquiry-detail", kwargs={"inquiry_number": number})

        self.client.force_authenticate(self.admin)
        detail = self.client.get(url).json()
        self.assertEqual(detail["data"]["message"], "We would love to trek in the spring.")
        self.assertEqual(detail["message"], "Request successful.")

        patched = self.client.patch(url, {"status": InquiryStatus.IN_CONTACT}, format="json").json()
        self.assertEqual(patched["data"]["message"], "We would love to trek in the spring.")

    def test_message_only_bodies_still_become_the_envelope_message(self):
        import json

        from apps.common.renderers import DreamscapeJSONRenderer

        body = json.loads(DreamscapeJSONRenderer().render({"message": "Logged out successfully."}))
        self.assertEqual(body["message"], "Logged out successfully.")
        self.assertEqual(body["data"], {})


class CRMAccessMatrixTests(CRMJobTestBase):
    """Every CRM endpoint, hit as anonymous, customer, sales agent, and admin."""

    def setUp(self):
        super().setUp()
        self.lead = self.make_lead(customer=Customer.objects.create(email="matrix@example.com"), email="matrix@example.com")
        self.task = self.make_task(self.lead, timedelta(days=1))
        self.rule = LeadAssignmentRule.objects.create(agent=self.annapurna_agent, trip=self.trip)
        ref = {"inquiry_number": self.lead.inquiry_number}
        # (url, admin_only)
        self.endpoints = [
            (reverse("inquiries:inquiry-list-create"), False),
            (reverse("inquiries:tag-list-create"), False),
            (reverse("inquiries:my-tasks"), False),
            (reverse("inquiries:task-detail", kwargs={"pk": self.task.id}), False),
            (reverse("inquiries:crm-pipeline-summary"), False),
            (reverse("inquiries:crm-funnel"), False),
            (reverse("inquiries:crm-trek-pipeline"), False),
            (reverse("inquiries:crm-customer-detail", kwargs={"email": "matrix@example.com"}), False),
            (reverse("inquiries:crm-leads-by-departure"), False),
            (reverse("inquiries:inquiry-detail", kwargs=ref), False),
            (reverse("inquiries:inquiry-notes", kwargs=ref), False),
            (reverse("inquiries:inquiry-timeline", kwargs=ref), False),
            (reverse("inquiries:inquiry-activities", kwargs=ref), False),
            (reverse("inquiries:inquiry-tasks", kwargs=ref), False),
            (reverse("inquiries:crm-assignment-rules"), True),
            (reverse("inquiries:crm-assignment-rule-detail", kwargs={"pk": self.rule.id}), True),
        ]

    def assert_get(self, expected_for):
        for url, admin_only in self.endpoints:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, expected_for(admin_only))

    def test_anonymous_is_unauthorised_everywhere(self):
        self.client.force_authenticate(None)
        self.assert_get(lambda admin_only: status.HTTP_401_UNAUTHORIZED)

    def test_customer_is_forbidden_everywhere(self):
        self.client.force_authenticate(self.customer)
        self.assert_get(lambda admin_only: status.HTTP_403_FORBIDDEN)

    def test_sales_agent_sees_crm_but_not_admin_config(self):
        self.client.force_authenticate(self.annapurna_agent)
        self.assert_get(lambda admin_only: status.HTTP_403_FORBIDDEN if admin_only else status.HTTP_200_OK)

    def test_admin_sees_everything(self):
        self.client.force_authenticate(self.admin)
        self.assert_get(lambda admin_only: status.HTTP_200_OK)

    def test_bulk_assign_is_admin_only(self):
        url = reverse("inquiries:crm-bulk-assign")
        for user, expected in ((None, 401), (self.customer, 403), (self.annapurna_agent, 403)):
            with self.subTest(user=user):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.post(url, {}, format="json").status_code, expected)
