from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0004_order_salesforce_sync"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="salesforce_order_id",
            field=models.CharField(blank=True, max_length=18),
        ),
    ]
