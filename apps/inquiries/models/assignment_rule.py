from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models.base import TimeStampedModel

#: Lead statuses that still need an owner. Shared with the capacity counters so
#: "open leads" means the same thing on the CRM board and the capacity board.
OPEN_LEAD_STATUSES = ("NEW", "ASSIGNED", "IN_CONTACT")


class LeadAssignmentRule(TimeStampedModel):
    """
    Routes inbound leads to a specialist agent by what they are asking about.

    A rule targets a departure, a trip, or a destination. The most specific
    match wins — a rule for the March Annapurna departure beats a rule for
    Annapurna in general, which beats a rule for Nepal. When nothing matches
    the lead stays unassigned, which is the behaviour that predates rules.
    """

    #: Higher specificity is resolved first. Mirrors the branch order in
    #: ``resolve_agent``; kept as data so the ordering is expressible in SQL.
    SPECIFICITY = {"departure": 3, "trip": 2, "destination": 1}

    departure = models.ForeignKey(
        "trips.TripDeparture",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assignment_rules",
    )
    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assignment_rules",
    )
    destination = models.ForeignKey(
        "destinations.Destination",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assignment_rules",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lead_assignment_rules",
    )
    priority = models.IntegerField(
        default=0,
        help_text="Tie-breaker within the same specificity. Higher wins.",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "crm_lead_assignment_rules"
        ordering = ["-priority", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(departure__isnull=False)
                    | Q(trip__isnull=False)
                    | Q(destination__isnull=False)
                ),
                name="assignment_rule_requires_a_target",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "departure"], name="rule_active_dep_idx"),
            models.Index(fields=["is_active", "trip"], name="rule_active_trip_idx"),
        ]

    @property
    def target_label(self) -> str:
        if self.departure_id:
            return f"{self.departure.trip.title} — {self.departure.start_date}"
        if self.trip_id:
            return self.trip.title
        if self.destination_id:
            return self.destination.name
        return "—"

    def __str__(self):
        return f"{self.target_label} -> {self.agent}"


def resolve_agent(inquiry):
    """
    Find the agent a lead should go to, or None.

    Checked most specific first; the first tier with a match wins outright, so
    a broad destination rule never overrides a departure-level one.
    """
    base = LeadAssignmentRule.objects.filter(is_active=True).select_related("agent")

    tiers = []
    if inquiry.departure_id:
        tiers.append(base.filter(departure_id=inquiry.departure_id))
    if inquiry.trip_id:
        tiers.append(base.filter(trip_id=inquiry.trip_id, departure__isnull=True))
        destination_id = inquiry.trip.destination_id
        tiers.append(
            base.filter(
                destination_id=destination_id,
                trip__isnull=True,
                departure__isnull=True,
            )
        )

    for tier in tiers:
        rule = tier.order_by("-priority", "created_at").first()
        if rule and rule.agent.is_active:
            return rule.agent
    return None
