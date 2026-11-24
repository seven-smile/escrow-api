from rest_framework import serializers

from .models import Trade


class TradeSerializer(serializers.ModelSerializer):
    seller = serializers.CharField(source="seller.username", read_only=True)
    buyer = serializers.CharField(source="buyer.username", read_only=True)

    class Meta:
        model = Trade
        fields = ["id", "seller", "buyer", "currency", "amount", "status", "created_at"]