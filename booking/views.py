from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import OrderForm, SignUpForm
from .models import DELIVERY_FEE, MIN_ORDER, Order, OrderItem
from .salesforce import sync_order_to_salesforce


def health_check(request):
    return HttpResponse("ok")


def send_welcome_email(request, user):
    link = request.build_absolute_uri(reverse("order"))
    send_mail(
        subject="Welcome to Aysha Pharmacy",
        message=(f"Hi {user.username},\n\nYour account is ready. Shop health and personal-care "
                 f"essentials and track them from the My orders page.\n\nOrder now: {link}\n\nAysha Pharmacy"),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def signup(request):
    if request.user.is_authenticated:
        return redirect("order")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        send_welcome_email(request, user)
        login(request, user)
        return redirect("order")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def place_order(request):
    initial = {"name": request.user.get_full_name() or request.user.username, "email": request.user.email}
    form = OrderForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user, name=d["name"], phone=d["phone"], email=d["email"],
                fulfilment=d["fulfilment"], address=d["address"], date=d["date"], time=d["time"],
                notes=d["notes"], subtotal=form.subtotal, delivery_fee=form.delivery_fee, total=form.total,
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        product=product,
                        product_code=product.slug,
                        product_name=product.name,
                        quantity=quantity,
                        unit_price=product.price,
                    )
                    for product, quantity in form.lines
                ]
            )
        if not sync_order_to_salesforce(order):
            messages.warning(
                request,
                "Your order was placed, but it has not synced to Salesforce. "
                "The shop administrator can retry the sync.",
            )
        return redirect("success", reference=order.reference)
    return render(request, "booking/order.html", {"form": form, "delivery_fee": DELIVERY_FEE, "min_order": MIN_ORDER})


@login_required
def success(request, reference):
    order = get_object_or_404(Order, reference=reference, user=request.user)
    return render(request, "booking/success.html", {"order": order})


@login_required
def my_orders(request):
    orders = request.user.orders.prefetch_related("items")
    return render(request, "booking/my_orders.html", {"orders": orders})


@login_required
@require_POST
def cancel(request, reference):
    order = get_object_or_404(Order, reference=reference, user=request.user)
    if order.status == "pending":
        order.status = "cancelled"
        order.save(update_fields=["status"])
        messages.success(request, f"Order {order.reference} cancelled.")
    else:
        messages.error(request, "This order is already being prepared. Please call us to change it.")
    return redirect("my_orders")
