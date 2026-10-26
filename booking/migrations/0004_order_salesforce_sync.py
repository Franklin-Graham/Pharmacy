from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0003_order_orderitem_delete_booking"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="salesforce_contact_id",
            field=models.CharField(blank=True, max_length=18),
        ),
        migrations.AddField(
            model_name="order",
            name="salesforce_opportunity_id",
            field=models.CharField(blank=True, max_length=18),
        ),
        migrations.AddField(
            model_name="order",
            name="salesforce_sync_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="salesforce_sync_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("synced", "Synced"),
                    ("failed", "Failed"),
                    ("not_configured", "Not configured"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
