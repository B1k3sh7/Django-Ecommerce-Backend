from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.db import transaction
from core.models import Order
from .serializers import PaymentSerializer
import stripe
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentViewSet(viewsets.ViewSet):

    def create(self, request):
        serializer = PaymentSerializer(data=request.data)

        if serializer.is_valid():
            order_id = serializer.validated_data.get('order_id')
            try:
                with transaction.atomic():
                    order = Order.objects.get(id=order_id)

                    total_amount = order.total_amount()

                    payment_intent = stripe.PaymentIntent.create(
                        amount=int(total_amount * 100),
                        currency=serializer.validated_data['currency'],
                        payment_method_types=serializer.validated_data['payment_method_types']
                    )

                    order.payment_intent_id = payment_intent.id
                    order.save()

                return Response({
                    'payment_intent_id': payment_intent.id,
                    'client_secret': payment_intent.client_secret
                }, status=status.HTTP_201_CREATED)

            except Order.DoesNotExist:
                return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
            except stripe.error.CardError as e:
                logger.error(f'CardError: {str(e)}')
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except stripe.error.StripeError as e:
                logger.error(f'StripeError: {str(e)}')
                return Response({'error': 'Something went wrong with Stripe processing'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    def post(self, request):
        event = None
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except ValueError as e:
            logger.error(f'ValueError: {str(e)}')
            return JsonResponse({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f'SignatureVerificationError: {str(e)}')
            return JsonResponse({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Unexpected error: {str(e)}')
            return JsonResponse({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        event_id = event['id']
        event_type = event['type']
        logger.info(f'Handling event {event_id} of type {event_type}')

        # Handle the event type
        if event['type'] == 'payment_intent.succeeded':
            payment_intent_id = event['data']['object']['id']
            try:
                order = Order.objects.get(payment_intent_id=payment_intent_id)
                order.status = 'paid'
                order.save(update_fields=['status'])
                return JsonResponse({'message': 'Payment succeeded'}, status=status.HTTP_200_OK)
            except Order.DoesNotExist:
                logger.error(f'Order with payment_intent_id {payment_intent_id} does not exist.')
                return JsonResponse({'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        elif event['type'] == 'payment_intent.failed':
            payment_intent_id = event['data']['object']['id']
            try:
                order = Order.objects.get(payment_intent_id=payment_intent_id)
                order.status = 'failed'
                order.save(update_fields=['status'])
                return JsonResponse({'message': 'Payment failed'}, status=status.HTTP_400_BAD_REQUEST)
            except Order.DoesNotExist:
                logger.error(f'Order with payment_intent_id {payment_intent_id} does not exist.')
                return JsonResponse({'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return JsonResponse({'message': 'Unknown webhook event'}, status=status.HTTP_400_BAD_REQUEST)
