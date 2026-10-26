import datetime
import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import DELIVERY_FEE, MIN_ORDER, Order, Product

ADVANCE_DAYS = 7
MAX_ORDERS_PER_SLOT = 10
MAX_QTY = 20
SLOTS = [
    (datetime.time(h, m).strftime("%H:%M"), datetime.time(h, m).strftime("%I:%M %p"))
    for h in range(11, 22) for m in (0, 30)
]


class OrderForm(forms.Form):
    fulfilment = forms.ChoiceField(choices=Order.FULFILMENT, widget=forms.RadioSelect, initial="delivery")
    name = forms.CharField(label="Full name", max_length=100, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    phone = forms.CharField(label="Mobile number", max_length=15, widget=forms.TextInput(attrs={"placeholder": "10-digit mobile number", "inputmode": "numeric", "autocomplete": "tel"}))
    email = forms.EmailField(label="Email (optional)", required=False)
    address = forms.CharField(label="Delivery address", required=False, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "House no., street, area, landmark"}))
    date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.ChoiceField(label="Time", choices=[("", "Choose a time")] + SLOTS)
    notes = forms.CharField(
        label="Order notes (optional)",
        required=False,
        max_length=300,
        widget=forms.Textarea(attrs={
            "rows": 2,
            "placeholder": "Delivery instructions or other order details",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["date"].widget.attrs["min"] = today.isoformat()
        self.fields["date"].widget.attrs["max"] = (today + datetime.timedelta(days=ADVANCE_DAYS)).isoformat()
        self.products = list(Product.objects.filter(is_active=True))
        for product in self.products:
            self.fields[f"qty_{product.slug}"] = forms.IntegerField(
                label=product.name,
                min_value=0,
                max_value=MAX_QTY,
                initial=0,
                required=False,
                widget=forms.NumberInput(attrs={
                    "min": 0,
                    "max": MAX_QTY,
                    "data-price": product.price,
                }),
            )

    def product_rows(self):
        return [(self[f"qty_{product.slug}"], product) for product in self.products]

    def clean_phone(self):
        digits = re.sub(r"[\s\-+]", "", self.cleaned_data["phone"])
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if not re.fullmatch(r"[6-9]\d{9}", digits):
            raise forms.ValidationError("Enter a valid 10-digit mobile number.")
        return digits

    def clean_date(self):
        d = self.cleaned_data["date"]
        today = timezone.localdate()
        if d < today:
            raise forms.ValidationError("Choose today or a future date.")
        if d > today + datetime.timedelta(days=ADVANCE_DAYS):
            raise forms.ValidationError(f"You can order up to {ADVANCE_DAYS} days ahead.")
        return d

    def clean_time(self):
        return datetime.datetime.strptime(self.cleaned_data["time"], "%H:%M").time()

    def clean(self):
        data = super().clean()
        self.lines, subtotal = [], 0
        for product in self.products:
            qty = data.get(f"qty_{product.slug}") or 0
            if qty:
                self.lines.append((product, qty))
                subtotal += qty * product.price
        if not self.lines:
            raise forms.ValidationError("Add at least one product to your order.")
        if subtotal < MIN_ORDER:
            raise forms.ValidationError(f"The minimum order is ₹{MIN_ORDER}.")
        delivery = data.get("fulfilment") == "delivery"
        if delivery and not (data.get("address") or "").strip():
            self.add_error("address", "Enter your delivery address.")
        self.subtotal = subtotal
        self.delivery_fee = DELIVERY_FEE if delivery else 0
        self.total = subtotal + self.delivery_fee
        d, t = data.get("date"), data.get("time")
        if d and t:
            now = timezone.localtime()
            if d == now.date() and t <= now.time():
                self.add_error("time", "That time has passed. Choose a later slot.")
            elif (
                Order.objects.filter(
                    date=d, time=t, items__product__isnull=False
                )
                .exclude(status="cancelled")
                .distinct()
                .count()
                >= MAX_ORDERS_PER_SLOT
            ):
                self.add_error("time", "This slot is full. Please pick another time.")
        return data


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
