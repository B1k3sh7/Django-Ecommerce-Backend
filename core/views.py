from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from .models import *
from .serializers import *
from payment.serializers import PaymentSerializer
from .pagination import CustomPageNumberPagination, AnotherCustomPageNumberPagination

import logging

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ModelViewSet):
  queryset = Category.objects.all()
  serializer_class = CategorySerializer


class BrandViewSet(viewsets.ModelViewSet):
  queryset = Brand.objects.all()
  serializer_class = BrandSerializer

  
class ProductViewSet(viewsets.ModelViewSet):
  queryset = Product.objects.all()
  serializer_class = ProductSerializer
  filter_backends = [filters.OrderingFilter, filters.SearchFilter]
  search_fields = ['name']
  ordering_fields = ['price', 'name']
  pagination_class = CustomPageNumberPagination


class OrderViewSet(viewsets.ModelViewSet):
  queryset = Order.objects.all()
  serializer_class = OrderSerializer
  permission_classes = [IsAuthenticated]
  pagination_class = AnotherCustomPageNumberPagination


  def get_queryset(self):
    user = self.request.user
    return Order.objects.filter(user=user)

  def create(self, request, *args, **kwargs):
    try:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = self.perform_create(serializer)
        self._create_order_items(order)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    except Exception as e:
        logger.error(f"Error creating order: {e}", exc_info=True)
        return Response({'error': 'An error occurred while creating the order.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

  def perform_create(self, serializer):
    order = serializer.save(user=self.request.user)
    self._create_order_items(order)

    self._create_shipping_detail(order)

    return order

  def _create_order_items(self, order):
    order_items_data = self.request.data.get('order_items', [])
    serializer = OrderItemSerializer(data=order_items_data, many=True, context={'order_id': order.id})
    if serializer.is_valid():
        serializer.save()
    else:
        raise serializers.ValidationError(serializer.errors)
    


  def _create_shipping_detail(self, order):
    shipping_method_id = self.request.data.get('shipping_method')
    if shipping_method_id:
      shipping_method = ShippingMethod.objects.get(id=shipping_method_id)
      ShippingDetail.objects.create(order=order, shipping_method=shipping_method)
    
  
  @action(detail=True, methods=['get'])
  def track(self, request, pk=None):
    order = self.get_object()
    shipping_detail = ShippingDetail.objects.filter(order=order).first()
    if not shipping_detail:
      return Response({'error': 'No shipping details found for this order'}, status=status.HTTP_404_NOT_FOUND)
    
    data = {
      'tracking_number': shipping_detail.tracking_number,
      'shipped_at': shipping_detail.shipped_at,
      'delivered_at': shipping_detail.delivered_at,
    }
    return Response(data)
  

    
  @action(detail=True, methods=['post'])
  def pay(self, request, pk=None):
    order = self.get_object()
    if order.status != 'pending':
      return Response({'error': 'Order is not pending'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = PaymentSerializer(data={'order_id': order.id})
    if serializer.is_valid():
      return self.perform_create(serializer)
    return Response(serializers.errors, status=status.HTTP_400_BAD_REQUEST)



class OrderItemViewSet(viewsets.ModelViewSet):
  queryset = OrderItem.objects.all()
  serializer_class = OrderItemSerializer
  permission_classes = [IsAuthenticated]
  pagination_class = AnotherCustomPageNumberPagination


class ReviewViewSet(viewsets.ModelViewSet):
  queryset = Review.objects.all()
  serializer_class = ReviewSerializer
  permission_classes = [IsAuthenticated]
  pagination_class = AnotherCustomPageNumberPagination


class CartViewSet(viewsets.ModelViewSet):
  queryset = Cart.objects.all()
  serializer_class = CartSerializer
  permission_classes = [IsAuthenticated]
  pagination_class = AnotherCustomPageNumberPagination


class CartItemViewSet(viewsets.ModelViewSet):
  queryset = CartItem.objects.all()
  serializer_class = CartItemSerializer
  permission_classes = [IsAuthenticated]
  pagination_class = AnotherCustomPageNumberPagination



class ShippingMethodViewSet(viewsets.ModelViewSet):
  queryset = ShippingMethod.objects.all()
  serializer_class = ShippingMethodSerializer



def update_tracking_number(order_id, tracking_number):
  try:
    shipping_detail = ShippingDetail.objects.get(order_id=order_id)
    shipping_detail.tracking_number = tracking_number
    shipping_detail.save()
  except ShippingDetail.DoesNotExist:
    raise ValueError("Shipping detail not found.")


class ShippingDetailViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShippingDetail.objects.all()
    serializer_class = ShippingDetailSerializer

    def retrieve(self, request, pk=None):
        try:
            shipping_detail = self.get_object()
            shipping_detail.update_tracking_info()
            serializer = self.get_serializer(shipping_detail)
            return Response(serializer.data)
        except ShippingDetail.DoesNotExist:
            return Response({'error': 'Tracking information not found.'}, status=status.HTTP_404_NOT_FOUND)

    
    @action(detail=False, methods=['post'], url_path='update-tracking')
    def update_tracking(self, request, *args, **kwargs):
      order_id =  request.data.get('order_id')
      tracking_number = request.data.get('tracking_number')

      if not order_id or not tracking_number:
        return Response({'error': 'Order ID and tracking number are required'}, status=status.HTTP_400_BAD_REQUEST)
      
      if update_tracking_number(order_id, tracking_number):
        return Response({'status': 'Tracking number updated successfully'}, status=status.HTTP_200_OK)
      else:
        return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

