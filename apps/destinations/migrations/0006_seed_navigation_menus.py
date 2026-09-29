from django.db import migrations

# The header menus as they were before they became editable. Slugs are the
# catalogue `kind` values existing links already use (/treks?kind=expeditions).
MENUS = [
    {"slug": "treks", "name": "Treks", "menu_type": "CATEGORIES", "old_code": "TREKS",
     "eyebrow": "NEPAL, ONE TRAIL AT A TIME", "title": "Find your mountain trail.",
     "intro": "Choose a region and explore the journeys that take you there.",
     "image": "222-78-imgNepalEverestBaseCampAndAmaDablamPeak", "all_label": "Explore all treks"},
    {"slug": "tours", "name": "Tours", "menu_type": "CATEGORIES", "old_code": "TOURS",
     "eyebrow": "A DIFFERENT WAY TO EXPLORE", "title": "More than mountains.",
     "intro": "Make time for Nepal’s wildlife, heritage and quieter moments.",
     "image": "222-520-imgHimalayanAlpineLakeAndPeaks", "all_label": "Explore all tours"},
    {"slug": "expeditions", "name": "Climbing", "menu_type": "CATEGORIES", "old_code": "CLIMBING",
     "eyebrow": "A LITTLE HIGHER", "title": "Your next summit.",
     "intro": "Browse climbing journeys by region and talk through the route with our team.",
     "image": "222-78-imgAnnapurnaRangeAndHighGlacialLakesNepal", "all_label": "Explore all climbing trips"},
    {"slug": "beyond-nepal", "name": "Beyond Nepal", "menu_type": "LINKS",
     "eyebrow": "BEYOND THE FAMILIAR", "title": "Keep exploring.",
     "intro": "Discover places and cultures beyond Nepal with a personally planned journey.",
     "image": "/images/trek-memories/mountain-amphitheatre.jpg", "all_label": "Explore beyond Nepal",
     "href": "/destinations/beyond-nepal", "links": [
         {"label": "Bhutan", "description": "Valleys, monasteries & living traditions", "href": "/treks?country=bhutan"},
         {"label": "Tibet", "description": "High plateaus & sacred landscapes", "href": "/treks?country=tibet"},
         {"label": "India", "description": "Himalayan landscapes & cultural journeys", "href": "/treks?country=india"},
     ]},
    {"slug": "company", "name": "Company", "menu_type": "LINKS",
     "eyebrow": "ROOTED IN NEPAL · SINCE 2005", "title": "The people behind your journey.",
     "intro": "Get to know Dreamscape, our approach and the people beside you on the trail.",
     "image": "/images/trek-memories/together-in-the-mountains.jpg", "all_label": "Get to know Dreamscape",
     "href": "/about", "links": [
         {"label": "About Us", "description": "Our story & where we come from", "href": "/about"},
         {"label": "Why Us", "description": "How we shape your journey", "href": "/about#our-approach"},
         {"label": "Our Team", "description": "The people behind the plans", "href": "/about#our-team"},
         {"label": "Our Guides", "description": "Meet the people who lead the way", "href": "/guides"},
         {"label": "Testimonials", "description": "Stories from our travellers", "href": "/reviews"},
     ]},
]


def seed(apps, schema_editor):
    NavigationMenu = apps.get_model("destinations", "NavigationMenu")
    ActivityCategory = apps.get_model("destinations", "ActivityCategory")
    for order, spec in enumerate(MENUS):
        spec = dict(spec)
        old_code = spec.pop("old_code", None)
        menu, _ = NavigationMenu.objects.get_or_create(slug=spec.pop("slug"), defaults={**spec, "sort_order": order})
        if old_code:
            ActivityCategory.objects.filter(menu=old_code).update(nav_menu=menu)


def unseed(apps, schema_editor):
    ActivityCategory = apps.get_model("destinations", "ActivityCategory")
    codes = {"treks": "TREKS", "tours": "TOURS", "expeditions": "CLIMBING"}
    for category in ActivityCategory.objects.exclude(nav_menu=None).select_related("nav_menu"):
        category.menu = codes.get(category.nav_menu.slug, "")
        category.save(update_fields=["menu"])


class Migration(migrations.Migration):
    dependencies = [
        ("destinations", "0005_navigation_menus"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
