from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    username = models.CharField(max_length=40, unique=True)
    email = models.EmailField(unique=True) 
    refresh_token = models.CharField(max_length=500, null=True, blank=True)
    
    def __str__(self):
        if self.first_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    