from django.contrib import admin, messages
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import Order, OrderItem, Product
from .salesforce import sync_order_to_salesforce


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product_name", "quantity", "unit_price")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("name", "unit_label", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        "reference", "name", "phone", "fulfilment", "date", "time", "total",
        "status_badge", "salesforce_sync_status",
    )
    list_filter = ("status", "fulfilment", "salesforce_sync_status", "date")
    search_fields = ("reference", "name", "phone")
    date_hierarchy = "date"
    readonly_fields = (
        "reference", "subtotal", "delivery_fee", "total", "created_at",
        "salesforce_contact_id", "salesforce_opportunity_id", "salesforce_order_id",
        "salesforce_sync_status", "salesforce_sync_error",
    )
    inlines = [OrderItemInline]
    actions = ["confirm", "preparing", "ready", "complete", "cancel", "sync_salesforce"]

    @display(description="Status", label={"pending": "warning", "confirmed": "info", "preparing": "info",
                                          "ready": "success", "completed": "success", "cancelled": "danger"})
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="Mark as confirmed")
    def confirm(self, request, queryset):
        queryset.update(status="confirmed")

    @admin.action(description="Mark as preparing")
    def preparing(self, request, queryset):
        queryset.update(status="preparing")

    @admin.action(description="Mark as ready (out for delivery or ready for pickup)")
    def ready(self, request, queryset):
        queryset.update(status="ready")

    @admin.action(description="Mark as completed")
    def complete(self, request, queryset):
        queryset.update(status="completed")

    @admin.action(description="Mark as cancelled")
    def cancel(self, request, queryset):
        queryset.update(status="cancelled")

    @admin.action(description="Sync selected orders to Salesforce")
    def sync_salesforce(self, request, queryset):
        synced = failed = 0
        for order in queryset:
            if sync_order_to_salesforce(order):
                synced += 1
            else:
                failed += 1
        if synced:
            self.message_user(
                request, f"{synced} order(s) synced to Salesforce.", messages.SUCCESS
            )
        if failed:
            self.message_user(
                request,
                f"{failed} order(s) were not synced. Check their Salesforce sync error.",
                messages.ERROR,
            )
