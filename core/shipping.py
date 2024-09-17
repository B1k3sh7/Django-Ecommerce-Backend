import requests
from django.conf import settings

class CarrierAPI:
  @staticmethod
  def get_tracking_info(tracking_number):
    url = f"settings.CARRIER_API_URL/{tracking_number}"
    headers = {
      'Authorization': f"Bearer {settings.CARRIER_API_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()