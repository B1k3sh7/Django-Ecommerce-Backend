from rest_framework import serializers
from .models import *

class CategorySerializer(serializers.ModelSerializer):
  class Meta:
    model = Category
    fields = '__all__'


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

    
class ProductSerializer(serializers.ModelSerializer):
  category = CategorySerializer(read_only=True)
  brand = BrandSerializer(read_only=True)

  category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), write_only=True, source='category')  
  brand_id = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all(), write_only=True, source='brand') 
    

  class Meta:
    model = Product
    fields = ['id', 'name', 'brand', 'brand_id', 'description', 'price', 'stock_quantity', 'category', 'category_id', 'image', 'created_at', 'updated_at']

  def create(self, validated_data):
    category = validated_data.pop('category', None)
    brand = validated_data.pop('brand', None)
    
    product = Product.objects.create(
        **validated_data,
        category=category,
        brand=brand
    )
    
    return product
    
  def validate_price(self, value):
    if value < 0:
        raise serializers.ValidationError("Price cannot be negative.")
    return value

  def validate_stock_quantity(self, value):
    if value < 0:
      raise serializers.ValidationError("Stock quantity cannot be negative.")
    return value


class OrderItemSerializer(serializers.ModelSerializer):
  product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='product', write_only=True)
  product = ProductSerializer(read_only=True)
  
  class Meta:
    model = OrderItem
    fields = ['id', 'order', 'product', 'product_id', 'quantity', 'price']
    read_only_fields = ['id', 'order']
  
  def validate(self, data):
    product = data.get('product') or Product.objects.get(pk=data['product_id'])
    quantity = data.get('quantity')

    if quantity <= 0:
        raise serializers.ValidationError("Quantity must be positive.")

    if quantity > product.stock_quantity:
        raise serializers.ValidationError("Not enough stock available.")

    return data
  
  
  def create(self, validated_data):
    order_id = self.context.get('order_id')
    if not order_id:
      order_id = self.initial_data.get('order')
    
    if order_id is None:
      raise serializers.ValidationError("Order ID is required.")
    
    
    try:
      order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
      raise serializers.ValidationError("order does not exist.")
    
    validated_data['order'] = order
    return super().create(validated_data)


class OrderSerializer(serializers.ModelSerializer):
  order_item = OrderItemSerializer(many=True, read_only=True)


  shipping_method = serializers.PrimaryKeyRelatedField(queryset=ShippingMethod.objects.all(), write_only=True)
  shipping_method_detail = serializers.StringRelatedField(source="shippingdetail.shipping_method", read_only=True)
  tracking_number = serializers.CharField(source="shippingdetail.tracking_number", read_only=True)
  shipped_at = serializers.DateTimeField(source="shippingdetail.shipped_at", read_only=True)
  delivered_at = serializers.DateTimeField(source="shippingdetail.delivered_at", read_only=True)


  class Meta:
    model = Order
    fields = [
      'id', 'user', 'order_date', 'status', 'shipping_address', 'created_at', 'payment_intent_id', 'order_item',
      'shipping_method', 'shipping_method_detail', 'tracking_number', 'shipped_at', 'delivered_at'
    ]


  def create(self, validated_data):
    order_items_data = validated_data.pop('order_item', [])
    order = Order.objects.create(**validated_data)
    
    for item_data in order_items_data:
        OrderItem.objects.create(order=order, **item_data)
    
    return order
  
  def validate_shipping_address(self, value):
    if not value.strip():
      raise serializers.ValidationError("Shipping address cannot be empty.")
    return value


class ReviewSerializer(serializers.ModelSerializer):
  class Meta:
    model = Review
    fields = '__all__'

  def validate_rating(self, value):
    if not (1 <= value <= 5):
      raise serializers.ValidationError("Rating must be between 1 and 5.")
    return value


class CartItemSerializer(serializers.ModelSerializer):
  product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
  
  class Meta:
    model = CartItem
    fields = '__all__'


class CartSerializer(serializers.ModelSerializer):
  cartitem = CartItemSerializer(many=True, read_only=True)

  class Meta:
    model = Cart
    fields = '__all__'



class ShippingMethodSerializer(serializers.ModelSerializer):
  class Meta:
    model = ShippingMethod
    fields = '__all__'


class ShippingDetailSerializer(serializers.ModelSerializer):
  class Meta:
    model = ShippingDetail
    fields = '__all__'

