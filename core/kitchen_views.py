from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from orders.models import Order, OrderItem
from payments.models import Payment
from delivery.models import Delivery, DeliverySlot
from users.models import DishiUser

def kitchen_required(func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        if request.user.role not in ['kitchen', 'owner']:
            return redirect('/')
        return func(request, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

def owner_required(func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'owner':
            return redirect('/')
        return func(request, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@kitchen_required
def kitchen_dashboard(request):
    today = timezone.localdate()
    orders = Order.objects.filter(
        created_at__date=today
    ).exclude(status__in=['CANCELLED','FAILED']).select_related(
        'user', 'delivery_time_slot', 'payment'
    ).prefetch_related('items__menu_combination')

    # Stats
    total = orders.count()
    paid = orders.filter(status='PAID').count()
    preparing = orders.filter(status='PREPARING').count()
    dispatched = orders.filter(status='DISPATCHED').count()
    delivered = orders.filter(status='DELIVERED').count()
    pending_payment = orders.filter(status='PENDING').count()

    # Group by meal
    meal_groups = {}
    for order in orders.filter(status__in=['PAID','PREPARING','DISPATCHED']):
        for item in order.items.all():
            name = item.menu_combination.name
            if name not in meal_groups:
                meal_groups[name] = {'count': 0, 'orders': []}
            meal_groups[name]['count'] += item.quantity
            meal_groups[name]['orders'].append(order.order_code)

    # Group by location (area-based)
    location_groups = {}
    for order in orders.filter(status__in=['PAID','PREPARING','DISPATCHED']):
        addr = order.delivery_address_text or 'Unknown'
        # Simplify to area (first part)
        area = addr.split(',')[0].strip() if ',' in addr else addr
        if area not in location_groups:
            location_groups[area] = []
        location_groups[area].append(order)

    # Pending payments to confirm
    pending_payments = Payment.objects.filter(status='PENDING').select_related('order__user')

    # Riders
    riders = DishiUser.objects.filter(role='rider', is_active=True)
    slots = DeliverySlot.objects.filter(is_active=True)

    ctx = {
        'orders': orders,
        'total': total, 'paid': paid, 'preparing': preparing,
        'dispatched': dispatched, 'delivered': delivered,
        'pending_payment': pending_payment,
        'meal_groups': meal_groups,
        'location_groups': location_groups,
        'pending_payments': pending_payments,
        'riders': riders,
        'slots': slots,
        'today': today,
    }
    return render(request, 'kitchen/dashboard.html', ctx)

@kitchen_required
def confirm_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.confirm(confirmed_by=request.user)
    from django.contrib import messages
    messages.success(request, f'Payment confirmed for {payment.order.order_code}')
    return redirect('/kitchen/')

@kitchen_required
def update_order_status(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get('status')
        valid = ['PAID','PREPARING','DISPATCHED','DELIVERED','CANCELLED','FAILED']
        if new_status in valid:
            order.status = new_status
            order.save()
            # Auto-create delivery record
            if new_status == 'DISPATCHED':
                rider_id = request.POST.get('rider_id')
                rider = None
                if rider_id:
                    try: rider = DishiUser.objects.get(id=rider_id, role='rider')
                    except: pass
                Delivery.objects.get_or_create(
                    order=order,
                    defaults={
                        'rider': rider,
                        'rider_name': rider.name if rider else request.POST.get('rider_name',''),
                        'rider_phone': rider.phone_number if rider else request.POST.get('rider_phone',''),
                        'slot': order.delivery_time_slot,
                        'status': 'DISPATCHED',
                    }
                )
    return redirect('/kitchen/')

@owner_required
def owner_dashboard(request):
    from menu.models import DailyMenu, MenuCombination
    from core.models import SiteSettings
    today = timezone.localdate()

    # Analytics
    orders_today = Order.objects.filter(created_at__date=today).exclude(status='CANCELLED')
    revenue_today = orders_today.filter(status__in=['PAID','PREPARING','DISPATCHED','DELIVERED']).aggregate(r=Sum('total_amount'))['r'] or 0
    orders_total = Order.objects.exclude(status='CANCELLED').count()
    revenue_total = Order.objects.filter(status__in=['PAID','PREPARING','DISPATCHED','DELIVERED']).aggregate(r=Sum('total_amount'))['r'] or 0
    completion_rate = 0
    if orders_today.count() > 0:
        completed = orders_today.filter(status='DELIVERED').count()
        completion_rate = round((completed / orders_today.count()) * 100)

    # Top meal
    top_meal = OrderItem.objects.filter(
        order__created_at__date=today
    ).values('menu_combination__name').annotate(
        total=Sum('quantity')
    ).order_by('-total').first()

    # Menu management
    menus = DailyMenu.objects.all()[:7]
    try:
        today_menu = DailyMenu.objects.get(date=today)
    except: today_menu = None

    site = SiteSettings.get()
    riders = DishiUser.objects.filter(role='rider')

    ctx = {
        'orders_today': orders_today.count(),
        'revenue_today': revenue_today,
        'orders_total': orders_total,
        'revenue_total': revenue_total,
        'completion_rate': completion_rate,
        'top_meal': top_meal,
        'menus': menus,
        'today_menu': today_menu,
        'site': site,
        'riders': riders,
        'today': today,
    }
    return render(request, 'owner/dashboard.html', ctx)

@owner_required
def create_menu(request):
    from menu.models import DailyMenu, MenuCombination
    from django.contrib import messages
    if request.method == 'POST':
        p = request.POST
        import datetime
        date_str = p.get('date')
        try:
            date = datetime.date.fromisoformat(date_str)
            menu, created = DailyMenu.objects.get_or_create(date=date, defaults={
                'day_name': date.strftime('%A'),
                'main_item': p.get('main_item',''),
                'cutoff_time': p.get('cutoff_time','11:00'),
                'is_active': True,
            })
            if not created:
                menu.main_item = p.get('main_item', menu.main_item)
                menu.cutoff_time = p.get('cutoff_time', menu.cutoff_time)
                menu.is_active = True
                menu.save()
            messages.success(request, f'Menu for {date} saved!')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('/owner/')

@owner_required
def add_combination(request, menu_id):
    from menu.models import DailyMenu, MenuCombination
    from django.contrib import messages
    if request.method == 'POST':
        menu = get_object_or_404(DailyMenu, id=menu_id)
        p = request.POST
        MenuCombination.objects.create(
            daily_menu=menu,
            name=p.get('name',''),
            description=p.get('description',''),
            price=p.get('price',0),
            max_quantity=p.get('max_quantity',50),
            is_available=True,
        )
        from django.contrib import messages
        messages.success(request, 'Combination added!')
    return redirect('/owner/')

@owner_required
def update_site_settings(request):
    from core.models import SiteSettings
    from django.contrib import messages
    if request.method == 'POST':
        site = SiteSettings.get()
        p = request.POST
        f = request.FILES
        for field in ['business_name','tagline','phone','email','address','mpesa_till','mpesa_paybill','mpesa_account','ordering_open_message','ordering_closed_message','about_text','chef_name','whatsapp_number','instagram_url','facebook_url']:
            if p.get(field): setattr(site, field, p[field])
        if 'logo' in f: site.logo = f['logo']
        if 'hero_image' in f: site.hero_image = f['hero_image']
        if 'chef_photo' in f: site.chef_photo = f['chef_photo']
        site.save()
        messages.success(request, 'Settings updated!')
    return redirect('/owner/')
