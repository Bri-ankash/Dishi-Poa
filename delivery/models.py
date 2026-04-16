from django.db import models

class DeliverySlot(models.Model):
    label = models.CharField(max_length=30)  # "12:30 – 12:45"
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    order_position = models.PositiveIntegerField(default=0)

    @property
    def bookings_count(self):
        from orders.models import Order
        return Order.objects.filter(
            delivery_time_slot=self,
            status__in=['PENDING','PAID','PREPARING','DISPATCHED']
        ).count()

    @property
    def is_full(self): return self.bookings_count >= self.capacity

    @property
    def slots_left(self): return max(0, self.capacity - self.bookings_count)

    def __str__(self): return self.label

    class Meta:
        ordering = ['order_position', 'start_time']

class Delivery(models.Model):
    STATUS = [('PENDING','Pending'),('ASSIGNED','Assigned'),('DISPATCHED','Dispatched'),('DELIVERED','Delivered')]
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='delivery')
    rider = models.ForeignKey('users.DishiUser', on_delete=models.SET_NULL, null=True, blank=True)
    rider_name = models.CharField(max_length=100, blank=True)
    rider_phone = models.CharField(max_length=20, blank=True)
    slot = models.ForeignKey(DeliverySlot, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS, default='PENDING')
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self): return f"Delivery: {self.order.order_code}"
