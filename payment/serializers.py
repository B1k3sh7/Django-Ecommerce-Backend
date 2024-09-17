from rest_framework import serializers


CURRENCY_CHOICES = ['usd', 'eur', 'gbp']
PAYMENT_METHOD_TYPES = ['card']

class PaymentSerializer(serializers.Serializer):
  amount = serializers.DecimalField(max_digits=10, decimal_places=2)
  currency = serializers.ChoiceField(choices=CURRENCY_CHOICES, default='usd')
  payment_method_types = serializers.ListField(child=serializers.ChoiceField(choices=PAYMENT_METHOD_TYPES), default=[PAYMENT_METHOD_TYPES[0]])
  order_id = serializers.IntegerField()
