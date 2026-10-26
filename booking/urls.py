from django.urls import path
from . import views

urlpatterns = [
    path("", views.place_order, name="order"),
    path("order/<str:reference>/", views.success, name="success"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("my-orders/<str:reference>/cancel/", views.cancel, name="cancel"),
    path("accounts/signup/", views.signup, name="signup"),
]
