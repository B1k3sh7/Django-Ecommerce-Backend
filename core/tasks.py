from celery import shared_task
from .models import ShippingDetail

@shared_task
def update_all_tracking_info():
  for detail in ShippingDetail.objects.filter(tracking_number__isnull=False):
    detail.update_tracking_info()
