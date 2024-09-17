from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
from django.db import transaction
import logging

from .shipping import CarrierAPI

logger = logging.getLogger(__name__)

CustomUser = get_user_model()


class Category(models.Model):
  category_name = models.CharField(max_length=200)
  created_at = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    return self.category_name
  
  class Meta:
    indexes = [
      models.Index(fields=['category_name']),
    ]



class Brand(models.Model):
  name = models.CharField(max_length=255)

  def __str__(self):
      return self.name 



class Product(models.Model):
  name = models.CharField(max_length=255)
  brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
  description = models.TextField()
  image = models.ImageField(upload_to='product_img')
  price = models.DecimalField(max_digits=10, decimal_places=2)
  stock_quantity = models.PositiveIntegerField()
  category = models.ForeignKey(Category, on_delete=models.CASCADE)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  def __str__(self):
    return self.name
  
  
  def clean(self):
    if self.price < 0:
        raise ValidationError("Price cannot be negative.")
    if self.stock_quantity < 0:
        raise ValidationError("Stock quantity cannot be negative.")
  
  
  def update_stock(self, quantity):
    if quantity < 0:
      current_stock = Product.objects.filter(id=self.id).values('stock_quantity').first()
      
      if current_stock is None:
          raise ValidationError("Product does not exist.")
      if abs(quantity) > current_stock['stock_quantity']:
          raise ValidationError("Insufficient stock to fulfill this order")
    
    Product.objects.filter(id=self.id).update(stock_quantity=F('stock_quantity') + quantity)

  
  def total_value(self):
    return self.price * self.stock_quantity

  
  class Meta:
    indexes = [
      models.Index(fields=['name', 'category']),
    ]



class Order(models.Model):
  STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('shipped', 'Shipped'),
    ('delivered', 'Delivered'),
    ('canceled', 'Canceled'),
  ]
  
  user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
  order_date = models.DateTimeField(auto_now_add=True)
  status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
  shipping_address = models.TextField()
  created_at = models.DateTimeField(auto_now_add=True)
  payment_intent_id = models.CharField(max_length=255, null=True, blank=True)

  def __str__(self):
    return f"Order {self.id} by {self.user.username}"
  
  
  def clean(self):
      if not self.shipping_address.strip():
          raise ValidationError("Shipping address cannot be empty.")
  
  
  def total_amount(self):
    return sum(item.price * item.quantity for item in self.orderitem_set.all())
  
  
  class Meta:
    indexes = [
      models.Index(fields=['user', 'order_date']),
    ]



class OrderItem(models.Model):
  order = models.ForeignKey(Order, on_delete=models.CASCADE)
  product = models.ForeignKey(Product, on_delete=models.CASCADE)
  quantity = models.PositiveIntegerField()
  price = models.DecimalField(max_digits=10, decimal_places=2)

  def save(self, *args, **kwargs):
    with transaction.atomic(): 
      if self.pk is None:
        self.product.update_stock(-self.quantity)
      else: 
        old_quantity = OrderItem.objects.get(pk=self.pk).quantity
        if self.quantity > self.product.stock_quantity + old_quantity:
          raise ValidationError("Insufficient stock to fulfill this order.")
        difference = self.quantity - old_quantity
        self.product.update_stock(-difference)
      super().save(*args, **kwargs)

  
  def delete(self, *args, **kwargs):
    self.product.update_stock(self.quantity)
    super().delete(*args, **kwargs)

  
  class Meta:
    indexes = [
      models.Index(fields=['order', 'product']),
  ]



class Review(models.Model):
  RATING_CHOICES = [
    (1, '1 Star'),
    (2, '2 Stars'),
    (3, '3 Stars'),
    (4, '4 Stars'),
    (5, '5 Stars'),
  ]
  
  user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
  product = models.ForeignKey(Product, on_delete=models.CASCADE)
  rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default='1')
  comment = models.TextField()
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    unique_together = ('user', 'product')
    indexes = [
      models.Index(fields=['user', 'product']),
    ]



class Cart(models.Model):
  user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    indexes = [
      models.Index(fields=['user']),
    ]



class CartItem(models.Model):
  cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
  product = models.ForeignKey(Product, on_delete=models.CASCADE)
  quantity = models.PositiveIntegerField()

  class Meta:
    indexes = [
      models.Index(fields=['cart', 'product']),
    ]



@receiver(post_save, sender=OrderItem)
def update_product_stock_on__orderitem_save(sender, instance, **kwargs):
  try:
    with transaction.atomic():
      if kwargs.get('created', False):
        instance.product.update_stock(-instance.quantity)
      else:
        old_quantity = OrderItem.objects.get(pk=instance.pk).quantity
        difference = instance.quantity - old_quantity
        instance.product.update_stock(-difference)
  except Exception as e:
    logger.error(f"Error updating stock for product {instance.product_id}: {e}")
    raise




@receiver(post_delete, sender=OrderItem)
def update_product_stock_on_orderitem_delete(sender, instance, **kwargs):
  try:
    with transaction.atomic():
      instance.product.update_stock(instance.quantity)
  except Exception as e:
    logger.error(f"Error updating stock for product {instance.product_id}: {e}")
    raise



@receiver(post_save, sender=OrderItem)
def remove_cartitem_after_purchase(sender, instance, **kwargs):
  try:
    with transaction.atomic():
      CartItem.objects.filter(cart__user=instance.order.user, product=instance.product).delete()
      logger.info(f"Successfully removed cart item for product {instance.product_id} for user {instance.order.user_id}.")
  except Exception as e:
    logger.error(f"Error removing cart item for product {instance.product_id} for user {instance.order.user_id}: {e}")
    raise



class ShippingMethod(models.Model):
  name = models.CharField(max_length=200)
  rate = models.DecimalField(max_digits=5, decimal_places=2)

  def __str__(self):
      return self.name
  
  class Meta:
    indexes = [
      models.Index(fields=['name']),
    ]


class ShippingDetail(models.Model):
  order = models.OneToOneField(Order, on_delete=models.CASCADE)
  shipping_method = models.ForeignKey(ShippingMethod, on_delete=models.CASCADE)
  tracking_number = models.CharField(max_length=255, blank=True, null=True)
  shipped_at = models.DateTimeField(null=True, blank=True)
  delivered_at = models.DateTimeField(null=True, blank=True)
  
  def __str__(self):
      return f"Shipping detail for Order {self.order.id}"
  
  def update_tracking_info(self):
    if not self.tracking_number:
      return
    
    tracking_info = CarrierAPI.get_tracking_info(self.tracking_number)
    self.shipped_at = tracking_info.get("shipped_at", self.shipped_at)
    self.delivered_at = tracking_info.get("delivered_at", self.delivered_at)
    self.save()

  