import json
from datetime import time, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import OrderForm
from .models import Order, OrderItem, Product
from .salesforce import SalesforceClient


class SalesforceSyncTests(TestCase):
    def setUp(self):
        self.product = Product.objects.get(slug="adhesive-bandages")
        self.product.price = 220
        self.product.save(update_fields=["price"])
        self.order = Order.objects.create(
            name="Test Customer",
            phone="9876543210",
            email="customer@example.com",
            fulfilment="pickup",
            date=timezone.localdate(),
            time=time(12, 0),
            subtotal=220,
            total=220,
        )

    @staticmethod
    def response(payload):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(payload).encode("utf-8")
        return response

    @override_settings(
        SALESFORCE_CLIENT_ID="client-id",
        SALESFORCE_CLIENT_SECRET="client-secret",
        SALESFORCE_ACCOUNT_ID="001000000000001",
        SALESFORCE_LOGIN_URL="https://login.salesforce.com",
        SALESFORCE_API_VERSION="v60.0",
    )
    @patch("booking.salesforce.urlopen")
    def test_sync_creates_and_links_customer_and_order(self, urlopen):
        urlopen.side_effect = [
            self.response({
                "access_token": "access-token",
                "instance_url": "https://example.my.salesforce.com",
            }),
            self.response({"records": []}),
            self.response({"id": "003000000000001"}),
            self.response({"records": []}),
            self.response({"id": "006000000000001"}),
            self.response({"records": []}),
            self.response({"id": "00K000000000001"}),
            self.response({"records": []}),
            self.response({"id": "801000000000001"}),
        ]
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_code=self.product.slug,
            product_name=self.product.name,
            quantity=1,
            unit_price=self.product.price,
        )

        self.assertTrue(SalesforceClient().sync_order(self.order))

        self.order.refresh_from_db()
        self.assertEqual(self.order.salesforce_sync_status, "synced")
        self.assertEqual(self.order.salesforce_contact_id, "003000000000001")
        self.assertEqual(self.order.salesforce_opportunity_id, "006000000000001")
        self.assertEqual(self.order.salesforce_order_id, "801000000000001")
        self.assertEqual(urlopen.call_count, 9)
        contact_payload = json.loads(urlopen.call_args_list[2].args[0].data)
        opportunity_payload = json.loads(urlopen.call_args_list[4].args[0].data)
        order_payload = json.loads(urlopen.call_args_list[8].args[0].data)
        self.assertEqual(contact_payload["AccountId"], "001000000000001")
        self.assertEqual(contact_payload["Email"], "customer@example.com")
        self.assertEqual(opportunity_payload["Amount"], 220)
        self.assertIn(self.order.reference, opportunity_payload["Description"])
        self.assertIn("1 x Adhesive bandages", opportunity_payload["Description"])
        self.assertEqual(order_payload["AccountId"], "001000000000001")
        self.assertEqual(order_payload["EffectiveDate"], self.order.date.isoformat())
        self.assertEqual(order_payload["Status"], "Draft")
        self.assertIn(self.order.reference, order_payload["Description"])
        self.assertIn("total INR 220", order_payload["Description"])
        self.assertIn("1 x Adhesive bandages at INR 220 each", order_payload["Description"])

    @override_settings(
        SALESFORCE_CLIENT_ID="",
        SALESFORCE_CLIENT_SECRET="",
        SALESFORCE_ACCOUNT_ID="",
    )
    def test_sync_marks_order_not_configured_without_calling_salesforce(self):
        self.assertFalse(SalesforceClient().sync_order(self.order))

        self.order.refresh_from_db()
        self.assertEqual(self.order.salesforce_sync_status, "not_configured")
        self.assertIn("SALESFORCE_CLIENT_ID", self.order.salesforce_sync_error)


class PharmacyOrderFormTests(TestCase):
    def test_health_check_is_public(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_catalogue_page_shows_pharmacy_branding_and_sample_products(self):
        user = User.objects.create_user(username="pharmacy-customer", password="secret")
        self.client.force_login(user)

        response = self.client.get(reverse("order"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aysha Pharmacy")
        self.assertContains(response, "Adhesive bandages")
        self.assertContains(response, "Paracetamol 500 mg tablets")
        self.assertContains(response, "Prescription medicines are not available")
        self.assertNotContains(response, "Hot dum briyani")

    def test_active_catalogue_products_are_orderable_at_database_price(self):
        product = Product.objects.get(slug="digital-thermometer")
        Product.objects.create(
            name="Inactive product",
            slug="test-inactive-product",
            unit_label="each",
            price=100,
            is_active=False,
        )
        delivery_date = timezone.localdate() + timedelta(days=1)
        form = OrderForm(data={
            "fulfilment": "pickup",
            "name": "Test Customer",
            "phone": "9876543210",
            "email": "",
            "address": "",
            "date": delivery_date.isoformat(),
            "time": "13:00",
            "notes": "",
            "qty_digital-thermometer": "1",
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.subtotal, 180)
        self.assertEqual(form.total, 180)
        self.assertEqual(form.lines, [(product, 1)])
        self.assertNotIn("qty_test-inactive-product", form.fields)
