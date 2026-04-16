from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class DishiUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra):
        if not phone_number:
            raise ValueError('Phone number required')
        user = self.model(phone_number=phone_number, **extra)
        user.set_password(password)
        user.save()
        return user
    def create_superuser(self, phone_number, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', 'owner')
        return self.create_user(phone_number, password, **extra)

class DishiUser(AbstractBaseUser, PermissionsMixin):
    ROLES = [('customer','Customer'),('rider','Rider'),('kitchen','Kitchen'),('owner','Owner')]
    phone_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=20, choices=ROLES, default='customer')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []
    objects = DishiUserManager()
    def __str__(self): return f"{self.phone_number} ({self.role})"

class SavedLocation(models.Model):
    user = models.ForeignKey(DishiUser, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=50)  # "Office", "Home"
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    address_text = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.user.name or self.user.phone_number} — {self.name}: {self.address_text}"
