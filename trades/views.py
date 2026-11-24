from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Trade
from .serializers import TradeSerializer
from .services import (
    InvalidMove,
    NotAllowed,
    cancel_trade,
    mark_paid,
    open_dispute,
    release_trade,
)


def visible_trades(user):
    if user.is_staff:
        return Trade.objects.all()
    return Trade.objects.filter(Q(seller=user) | Q(buyer=user))


class MyTradesView(ListAPIView):
    serializer_class = TradeSerializer

    def get_queryset(self):
        user = self.request.user
        return Trade.objects.filter(Q(seller=user) | Q(buyer=user)).order_by("-created_at")


ACTIONS = {
    "mark-paid": mark_paid,
    "dispute": open_dispute,
    "cancel": cancel_trade,
    "release": release_trade,
}


class TradeActionView(APIView):
    def post(self, request, pk, action):
        if action not in ACTIONS:
            return Response({"detail": "Unknown action."}, status=status.HTTP_404_NOT_FOUND)

        trade = get_object_or_404(visible_trades(request.user), pk=pk)

        try:
            trade = ACTIONS[action](trade, request.user)
        except NotAllowed as error:
            return Response({"detail": str(error)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidMove as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)

        return Response(TradeSerializer(trade).data)