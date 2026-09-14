from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.accounts.models import UserRole
from apps.destinations.models import Destination, ActivityCategory
from apps.trips.models import Trip, TripDeparture


class PortalFixtures:
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        User = get_user_model()
        cls.admin = User.objects.create_user(email='admin@phase.test', password='StrongTestPass123!',
                                             role=UserRole.ADMIN, is_staff=True)
        cls.customer = User.objects.create_user(email='customer@phase.test', password='StrongTestPass123!')
        cls.destination = Destination.objects.create(name='Everest Nepal', slug='everest-nepal', country='NEPAL')
        cls.category = ActivityCategory.objects.create(name='Treks', slug='treks')
        cls.trip = Trip.objects.create(destination=cls.destination, category=cls.category,
            title='Everest Base Camp', slug='everest-base-camp', duration_days=14,
            difficulty_grade='GRADE_3', starting_price_usd=Decimal('1000'), overview='Everest trekking')
        cls.departure = TripDeparture.objects.create(trip=cls.trip,
            start_date=date.today() + timedelta(days=60), end_date=date.today() + timedelta(days=74),
            price_usd=1000, max_seats=10, available_seats=10)

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()
