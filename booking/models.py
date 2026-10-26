import random
import string
from django.conf import settings
from django.db import models

DELIVERY_FEE = 40
MIN_ORDER = 150

LEGACY_ITEM_NAMES = {
    "chicken": "Chicken briyani",
    "mutton": "Mutton briyani",
    "egg": "Egg briyani",
    "prawn": "Prawn briyani",
    "veg": "Vegetable briyani",
}


def make_reference():
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class Product(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.CharField(max_length=240, blank=True)
    unit_label = models.CharField(max_length=40, default="each")
    price = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Order(models.Model):
    FULFILMENT = [("delivery", "Delivery"), ("pickup", "Pickup")]
    SALESFORCE_SYNC_STATUS = [
        ("pending", "Pending"),
        ("synced", "Synced"),
        ("failed", "Failed"),
        ("not_configured", "Not configured"),
    ]
    STATUS = [
        ("pending", "Pending"), ("confirmed", "Confirmed"), ("preparing", "Preparing"),
        ("ready", "Ready"), ("completed", "Completed"), ("cancelled", "Cancelled"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    reference = models.CharField(max_length=12, unique=True, default=make_reference, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    fulfilment = models.CharField(max_length=10, choices=FULFILMENT, default="delivery")
    address = models.TextField(blank=True)
    date = models.DateField()
    time = models.TimeField()
    notes = models.TextField(blank=True, max_length=300)
    subtotal = models.PositiveIntegerField(default=0)
    delivery_fee = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    salesforce_contact_id = models.CharField(max_length=18, blank=True)
    salesforce_opportunity_id = models.CharField(max_length=18, blank=True)
    salesforce_order_id = models.CharField(max_length=18, blank=True)
    salesforce_sync_status = models.CharField(
        max_length=20, choices=SALESFORCE_SYNC_STATUS, default="pending"
    )
    salesforce_sync_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} - {self.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="order_items"
    )
    product_code = models.CharField(max_length=50)
    product_name = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveIntegerField()

    @property
    def name(self):
        if self.product_name:
            return self.product_name
        if self.product_id:
            return self.product.name
        return LEGACY_ITEM_NAMES.get(self.product_code, self.product_code)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity} x {self.name}"
