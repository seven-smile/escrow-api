from django.urls import path

from .views import MyWalletsView

urlpatterns = [
    path("wallets/", MyWalletsView.as_view(), name="my-wallets"),
]