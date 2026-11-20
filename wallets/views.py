from rest_framework.generics import ListAPIView

from .serializers import WalletSerializer


class MyWalletsView(ListAPIView):
    serializer_class = WalletSerializer

    def get_queryset(self):
        return self.request.user.wallets.all()