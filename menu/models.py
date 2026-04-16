from django.db import models

class DailyMenu(models.Model):
    date = models.DateField(unique=True, db_index=True)
    day_name = models.CharField(max_length=20)
    main_item = models.CharField(max_length=100)  # "Beef", "Fish"
    is_active = models.BooleanField(default=True)
    cutoff_time = models.TimeField(help_text="Orders close at this time e.g. 11:00")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.date} — {self.main_item}"

    @property
    def is_ordering_open(self):
        from django.utils import timezone
        now = timezone.localtime().time()
        return self.is_active and now < self.cutoff_time

    class Meta:
        ordering = ['-date']

class MenuCombination(models.Model):
    daily_menu = models.ForeignKey(DailyMenu, on_delete=models.CASCADE, related_name='combinations')
    name = models.CharField(max_length=200)  # "Ugali + Beef + Greens"
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    max_quantity = models.PositiveIntegerField(default=50)
    is_available = models.BooleanField(default=True)
    image = models.ImageField(upload_to='menu/', null=True, blank=True)
    order_position = models.PositiveIntegerField(default=0)

    def __str__(self): return f"{self.name} — KES {self.price}"

    @property
    def ordered_quantity(self):
        from orders.models import OrderItem
        from django.db.models import Sum
        result = OrderItem.objects.filter(
            menu_combination=self,
            order__status__in=['PENDING','PAID','PREPARING','DISPATCHED','DELIVERED']
        ).aggregate(total=Sum('quantity'))['total']
        return result or 0

    @property
    def remaining(self):
        return max(0, self.max_quantity - self.ordered_quantity)

    @property
    def is_sold_out(self):
        return self.remaining == 0

    class Meta:
        ordering = ['order_position', 'name']
