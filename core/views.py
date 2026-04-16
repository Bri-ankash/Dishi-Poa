from django.shortcuts import render, redirect
from django.utils import timezone
from .models import SiteSettings
from menu.models import DailyMenu
from orders.models import Order

def landing(request):
    site = SiteSettings.get()
    today = timezone.localdate()
    try:
        menu = DailyMenu.objects.get(date=today, is_active=True)
    except DailyMenu.DoesNotExist:
        menu = None
    return render(request, 'landing/index.html', {'site': site, 'menu': menu})
