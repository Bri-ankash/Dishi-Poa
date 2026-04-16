from django.db import models
from django.utils import timezone
from datetime import timedelta
import random, string

STATUS_CHOICES = [
    ('PENDING','Pending'),
    ('PAID','Paid'),
    ('PREPARING','Preparing'),
    ('DISPATCHED','Dispatched'),
    ('DELIVERED','Delivered'),
    ('CANCELLED','Cancelled'),
    ('FAILED','Failed'),
    ('REFUNDED','Refunded'),
]

def generate_order_code():
    date_str = timezone.localdate().strftime('%Y%m%d')
    count = Order.objects.filter(
        created_at__date=timezone.localdate()
    ).count() + 1
    return f"DP-{date_str}-{count:03d}"

class Order(models.Model):
    user = models.ForeignKey('users.DishiUser', on_delete=models.CASCADE, related_name='orders')
    order_code = models.CharField(max_length=30, unique=True, db_index=True)
    daily_order_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    delivery_location = models.ForeignKey('users.SavedLocation', on_delete=models.SET_NULL, null=True, blank=True)
    delivery_address_text = models.CharField(max_length=300, blank=True)
    delivery_latitude = models.FloatField(null=True, blank=True)
    delivery_longitude = models.FloatField(null=True, blank=True)
    delivery_time_slot = models.ForeignKey('delivery.DeliverySlot', on_delete=models.SET_NULL, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_reason = models.TextField(blank=True)
    refund_status = models.CharField(max_length=20, blank=True)

    def __str__(self): return f"{self.order_code} — {self.status}"

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = generate_order_code()
            self.daily_order_number = Order.objects.filter(
                created_at__date=timezone.localdate()
            ).count() + 1
        super().save(*args, **kwargs)

    @property
    def can_edit(self):
        """Exactly 10 minutes from creation — no cutoff dependency"""
        if self.status != 'PENDING':
            return False
        window = self.created_at + timedelta(minutes=10)
        return timezone.now() <= window

    @property
    def minutes_left_to_edit(self):
        if not self.can_edit: return 0
        window = self.created_at + timedelta(minutes=10)
        remaining = (window - timezone.now()).total_seconds() / 60
        return max(0, round(remaining, 1))

    @property
    def status_color(self):
        return {
            'PENDING':'#F59E0B', 'PAID':'#10B981', 'PREPARING':'#3B82F6',
            'DISPATCHED':'#8B5CF6', 'DELIVERED':'#059669',
            'CANCELLED':'#EF4444', 'FAILED':'#DC2626', 'REFUNDED':'#6B7280',
        }.get(self.status, '#666')

    class Meta:
        ordering = ['-created_at']

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_combination = models.ForeignKey('menu.MenuCombination', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.unit_price = self.menu_combination.price
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.menu_combination.name} x{self.quantity}"
