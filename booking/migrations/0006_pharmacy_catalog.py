from django.db import migrations, models
import django.db.models.deletion


SAMPLE_PRODUCTS = [
    {
        "name": "Adhesive bandages",
        "slug": "adhesive-bandages",
        "description": "Flexible adhesive strips for a home first-aid kit.",
        "unit_label": "pack of 10",
        "price": 60,
    },
    {
        "name": "Hand sanitizer",
        "slug": "hand-sanitizer",
        "description": "Portable hand sanitizer.",
        "unit_label": "100 ml bottle",
        "price": 75,
    },
    {
        "name": "Disposable face masks",
        "slug": "disposable-face-masks",
        "description": "Single-use face masks.",
        "unit_label": "pack of 5",
        "price": 50,
    },
    {
        "name": "Cotton wool",
        "slug": "cotton-wool",
        "description": "Soft cotton wool for general personal-care use.",
        "unit_label": "100 g pack",
        "price": 45,
    },
    {
        "name": "Digital thermometer",
        "slug": "digital-thermometer",
        "description": "Digital thermometer for home use.",
        "unit_label": "each",
        "price": 180,
    },
    {
        "name": "First-aid kit",
        "slug": "first-aid-kit",
        "description": "Compact starter kit with basic first-aid supplies.",
        "unit_label": "each",
        "price": 299,
    },
]

LEGACY_NAMES = {
    "chicken": "Chicken briyani",
    "mutton": "Mutton briyani",
    "egg": "Egg briyani",
    "prawn": "Prawn briyani",
    "veg": "Vegetable briyani",
}


def seed_products_and_preserve_order_items(apps, schema_editor):
    Product = apps.get_model("booking", "Product")
    OrderItem = apps.get_model("booking", "OrderItem")
    database = schema_editor.connection.alias

    for product in SAMPLE_PRODUCTS:
        Product.objects.using(database).get_or_create(
            slug=product["slug"],
            defaults={**product, "is_active": True},
        )
    for code, name in LEGACY_NAMES.items():
        OrderItem.objects.using(database).filter(
            product_code=code, product_name=""
        ).update(product_name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0005_order_salesforce_order_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name="ID",
                )),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=50, unique=True)),
                ("description", models.CharField(blank=True, max_length=240)),
                ("unit_label", models.CharField(default="each", max_length=40)),
                ("price", models.PositiveIntegerField()),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.RenameField(
            model_name="orderitem",
            old_name="dish",
            new_name="product_code",
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="product_code",
            field=models.CharField(max_length=50),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_items",
                to="booking.product",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_name",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(seed_products_and_preserve_order_items),
    ]
