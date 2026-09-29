from django.contrib.auth import get_user_model
from django.urls import reverse, reverse_lazy
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.common.testing import PortalFixtures
from apps.destinations.models import ActivityCategory, Destination, DestinationCountry, NavigationMenu

User = get_user_model()


class DestinationTests(APITestCase):
    """
    Test suite for Destinations & Activity Categories endpoints.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@dreamscapetreks.com",
            password="SecureAdminPassword123!",
            first_name="Admin",
            last_name="Superuser",
        )
        self.customer = User.objects.create_user(
            email="traveler@example.com",
            password="SecurePassword123!",
            first_name="Trekker",
            last_name="User",
            role=UserRole.CUSTOMER,
        )

        self.category = ActivityCategory.objects.create(
            name="Classic Trekking",
            slug="classic-trekking",
            description="High mountain lodge-to-lodge journeys.",
        )

        self.destination = Destination.objects.create(
            name="Everest Region",
            slug="everest-region",
            country=DestinationCountry.NEPAL,
            region_name="Khumbu",
            visa_guidelines="On-arrival visa available at Tribhuvan International Airport (KTM).",
            permit_details="Sagarmatha National Park Permit and Khumbu Pasang Lhamu Rural Municipality Permit required.",
            hero_media="https://images.dreamscapetreks.com/everest-hero.webp",
        )

    def test_list_destinations_public(self):
        url = reverse("destinations:destination-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertGreaterEqual(len(res["data"]["results"]), 1)
        # The seed migration adds the standard regions, so find this test's row.
        everest = next(row for row in res["data"]["results"] if row["slug"] == "everest-region")
        self.assertIn("trips_count", everest)

    def test_create_destination_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("destinations:destination-list")
        payload = {
            "name": "Annapurna Sanctuary",
            "slug": "annapurna-sanctuary",
            "country": DestinationCountry.NEPAL,
            "region_name": "Gandaki",
            "visa_guidelines": "Nepal on-arrival tourist visa.",
            "permit_details": "ACAP permit and TIMS card.",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["slug"], "annapurna-sanctuary")

    def test_create_destination_as_customer_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("destinations:destination-list")
        payload = {
            "name": "Langtang Valley",
            "slug": "langtang-valley",
            "country": DestinationCountry.NEPAL,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        res = response.json()
        self.assertFalse(res["success"])

    def test_get_destination_detail(self):
        url = reverse("destinations:destination-detail", kwargs={"slug": self.destination.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["slug"], "everest-region")
        self.assertIn("permit_details", res["data"])
        self.assertIn("schema_org_json_ld", res["data"])
        self.assertEqual(res["data"]["schema_org_json_ld"]["@type"], "TouristDestination")

    def test_patch_destination_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("destinations:destination-detail", kwargs={"slug": self.destination.slug})
        response = self.client.patch(url, {"region_name": "Solukhumbu High Himalaya"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertEqual(res["data"]["region_name"], "Solukhumbu High Himalaya")

    def test_list_and_create_categories(self):
        # Public GET
        list_url = reverse("destinations:category-list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])

        # Admin POST
        self.client.force_authenticate(user=self.admin)
        payload = {
            "name": "Mountaineering Expeditions",
            "slug": "mountaineering-expeditions",
            "description": "Technical 7,000m and 8,000m summit climbs.",
        }
        post_response = self.client.post(list_url, payload, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        res_post = post_response.json()
        self.assertEqual(res_post["data"]["slug"], "mountaineering-expeditions")


class MenuCategoryTests(PortalFixtures, APITestCase):
    """Categories with a `menu` are the header's Treks / Tours / Climbing sub-items."""

    list_url = reverse_lazy("destinations:category-list")

    def test_seeded_menu_items_match_the_previous_header(self):
        self.assertEqual(list(NavigationMenu.objects.values_list("slug", flat=True)), ["treks", "tours", "expeditions", "beyond-nepal", "company"])
        treks = ActivityCategory.objects.filter(menu__slug="treks")
        self.assertEqual(list(treks.values_list("slug", flat=True))[:2], ["everest", "langtang"])
        self.assertEqual(ActivityCategory.objects.filter(menu__slug="tours").count(), 5)
        self.assertEqual(
            set(ActivityCategory.objects.filter(menu__slug="expeditions").values_list("name", flat=True)),
            {"Everest Region", "Annapurna Region"},
        )

    def test_public_list_filters_by_menu_and_hides_hidden_items(self):
        ActivityCategory.objects.filter(slug="heli-tours").update(is_active=False)
        response = self.client.get(self.list_url, {"menu": "tours", "page_size": 100})
        slugs = [row["slug"] for row in response.json()["data"]["results"]]
        self.assertEqual(slugs, ["wildlife-tours", "luxury-tours", "culture-sightseeing", "day-tours"])
        self.assertIn("sort_order", response.json()["data"]["results"][0])

    def test_admin_creates_edits_and_reorders_a_menu_item(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(self.list_url, {"name": "Kanchenjunga Region", "slug": "kanchenjunga",
            "description": "Remote base camps in the far east", "menu": "treks", "sort_order": 99}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        url = reverse("destinations:category-detail", kwargs={"slug": "kanchenjunga"})
        patched = self.client.patch(url, {"description": "Base camps beneath the third-highest peak", "sort_order": 1}, format="json")
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(ActivityCategory.objects.get(slug="kanchenjunga").sort_order, 1)

    def test_same_label_allowed_in_different_menus_but_not_twice_in_one(self):
        self.client.force_authenticate(user=self.admin)
        duplicate = self.client.post(self.list_url, {"name": "Everest Region", "slug": "everest-again", "menu": "treks"}, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        other_menu = self.client.post(self.list_url, {"name": "Everest Region", "slug": "everest-tours", "menu": "tours"}, format="json")
        self.assertEqual(other_menu.status_code, status.HTTP_201_CREATED)

    def test_customer_cannot_change_menu_items(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("destinations:category-detail", kwargs={"slug": "everest"})
        self.assertEqual(self.client.patch(url, {"name": "Hijacked"}, format="json").status_code, status.HTTP_403_FORBIDDEN)

    def test_deleting_a_category_with_treks_is_refused_with_a_clear_message(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(reverse("destinations:category-detail", kwargs={"slug": self.category.slug}))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("1 trek is still in this category", response.json()["error"]["message"])
        self.assertTrue(ActivityCategory.objects.filter(pk=self.category.pk).exists())

    def test_trip_list_exposes_the_category_menu(self):
        self.trip.category = ActivityCategory.objects.get(slug="everest")
        self.trip.save(update_fields=["category"])
        row = next(r for r in self.client.get(reverse("trips:trip-list")).json()["data"]["results"] if r["slug"] == self.trip.slug)
        self.assertEqual((row["category_slug"], row["category_menu"]), ("everest", "treks"))

    def test_a_category_cannot_be_put_in_a_links_menu(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.list_url, {"name": "Nepal", "slug": "nepal-link", "menu": "company"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class NavigationMenuTests(PortalFixtures, APITestCase):
    """The top-level header menus, editable in admin → Settings."""

    list_url = reverse_lazy("destinations:nav-menu-list")

    def detail(self, slug):
        return reverse("destinations:nav-menu-detail", kwargs={"slug": slug})

    def test_public_list_has_menus_in_order_with_their_items(self):
        data = self.client.get(self.list_url).json()["data"]
        self.assertEqual([m["name"] for m in data], ["Treks", "Tours", "Climbing", "Beyond Nepal", "Company"])
        treks = data[0]
        self.assertEqual((treks["slug"], treks["menu_type"], treks["title"]), ("treks", "CATEGORIES", "Find your mountain trail."))
        self.assertEqual(treks["items"][0]["slug"], "everest")
        self.assertEqual([link["label"] for link in data[4]["links"]][:2], ["About Us", "Why Us"])

    def test_hidden_menus_and_items_are_left_out_for_the_public_only(self):
        NavigationMenu.objects.filter(slug="company").update(is_active=False)
        ActivityCategory.objects.filter(slug="mustang").update(is_active=False)
        public = self.client.get(self.list_url).json()["data"]
        self.assertNotIn("company", [m["slug"] for m in public])
        self.assertNotIn("mustang", [i["slug"] for i in public[0]["items"]])
        self.client.force_authenticate(user=self.admin)
        admin = self.client.get(self.list_url).json()["data"]
        self.assertIn("company", [m["slug"] for m in admin])
        self.assertIn("mustang", [i["slug"] for i in admin[0]["items"]])

    def test_admin_adds_a_new_trek_menu_and_lists_a_category_under_it(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(self.list_url, {"name": "Safaris", "menu_type": "CATEGORIES", "sort_order": 9, "title": "Into the jungle."}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.json()["data"]["slug"], "safaris")
        category = self.client.post(reverse("destinations:category-list"), {"name": "Chitwan", "slug": "chitwan", "menu": "safaris"}, format="json")
        self.assertEqual(category.status_code, status.HTTP_201_CREATED)
        menus = self.client.get(self.list_url).json()["data"]
        self.assertEqual(menus[-1]["items"][0]["slug"], "chitwan")

    def test_rename_and_reorder_keep_the_slug_and_type(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(self.detail("expeditions"), {"name": "Expeditions", "sort_order": 0, "slug": "changed", "menu_type": "LINKS"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        menu = NavigationMenu.objects.get(slug="expeditions")
        self.assertEqual((menu.name, menu.sort_order, menu.menu_type), ("Expeditions", 0, "CATEGORIES"))

    def test_link_menus_validate_their_links(self):
        self.client.force_authenticate(user=self.admin)
        bad = self.client.patch(self.detail("company"), {"links": [{"label": "Evil", "href": "javascript:alert(1)"}]}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        good = self.client.patch(self.detail("company"), {"links": [{"label": "Careers", "description": "Join us", "href": "/careers"}]}, format="json")
        self.assertEqual(good.status_code, status.HTTP_200_OK)
        self.assertEqual(NavigationMenu.objects.get(slug="company").links, [{"label": "Careers", "description": "Join us", "href": "/careers"}])

    def test_deleting_a_menu_with_items_is_refused_but_empty_menus_go(self):
        self.client.force_authenticate(user=self.admin)
        refused = self.client.delete(self.detail("tours"))
        self.assertEqual(refused.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("still has 5 items", refused.json()["error"]["message"])
        self.assertEqual(self.client.delete(self.detail("company")).status_code, status.HTTP_204_NO_CONTENT)

    def test_customers_cannot_change_menus(self):
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.patch(self.detail("treks"), {"name": "Hijacked"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(self.list_url, {"name": "Spam"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
