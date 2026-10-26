from django.db import migrations


SAMPLE_PRODUCTS = [
    {
        "name": "Paracetamol 500 mg tablets",
        "slug": "paracetamol-500mg",
        "description": "Sample non-prescription medicine listing. Confirm local sale requirements.",
        "unit_label": "pack of 10",
        "price": 20,
    },
    {
        "name": "Oral rehydration salts (ORS)",
        "slug": "oral-rehydration-salts",
        "description": "Sample non-prescription product listing. Confirm local sale requirements.",
        "unit_label": "sachet",
        "price": 20,
    },
]


def add_sample_products(apps, schema_editor):
    Product = apps.get_model("booking", "Product")
    database = schema_editor.connection.alias
    for product in SAMPLE_PRODUCTS:
        Product.objects.using(database).get_or_create(
            slug=product["slug"],
            defaults={**product, "is_active": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0006_pharmacy_catalog"),
    ]

    operations = [
        migrations.RunPython(add_sample_products, migrations.RunPython.noop),
    ]
