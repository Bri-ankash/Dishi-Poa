from django.db import models
from django.utils import timezone

class Payment(models.Model):
    STATUS = [('PENDING','Pending'),('CONFIRMED','Confirmed'),('FAILED','Failed'),('REFUNDED','Refunded')]
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_code = models.CharField(max_length=30, unique=True, db_index=True)
    mpesa_phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='PENDING')
    confirmed_by = models.ForeignKey('users.DishiUser', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # STK Push fields (Phase 2)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    stk_push_sent = models.BooleanField(default=False)

    def confirm(self, confirmed_by=None):
        self.status = 'CONFIRMED'
        self.confirmed_at = timezone.now()
        self.confirmed_by = confirmed_by
        self.save()
        self.order.status = 'PAID'
        self.order.save()

    def __str__(self): return f"{self.order.order_code} — {self.mpesa_code} — {self.status}"

    class Meta:
        ordering = ['-created_at']
