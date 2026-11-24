from django.urls import path

from .views import MyTradesView, TradeActionView

urlpatterns = [
    path("trades/", MyTradesView.as_view(), name="my-trades"),
    path("trades/<int:pk>/<str:action>/", TradeActionView.as_view(), name="trade-action"),
]