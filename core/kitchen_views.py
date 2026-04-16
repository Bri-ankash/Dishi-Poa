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
    from payments.models import Payment
    from orders.models import Order, STATUS_CHOICES
    from delivery.models import DeliverySlot, Delivery
    from users.models import DishiUser
    from landing.models import GalleryItem
    today = timezone.now().localdate() if hasattr(timezone.now(), 'localdate') else timezone.localdate()
    from django.db.models import Sum

    orders_today_qs = Order.objects.filter(created_at__date=today).exclude(status='CANCELLED')
    revenue_today = orders_today_qs.filter(status__in=["PAID","PREPARING","DISPATCHED","DELIVERED"]).aggregate(r=Sum("total_amount"))["r"] or 0
    orders_total = Order.objects.exclude(status="CANCELLED").count()
    revenue_total = Order.objects.filter(status__in=["PAID","PREPARING","DISPATCHED","DELIVERED"]).aggregate(r=Sum("total_amount"))["r"] or 0
    completion_rate = 0
    if orders_today_qs.count() > 0:
        completed = orders_today_qs.filter(status="DELIVERED").count()
        completion_rate = round((completed / orders_today_qs.count()) * 100)
    from django.db.models import Sum as DSum
    top_meal = None
    try:
        from orders.models import OrderItem
        from django.db.models import Sum as S2
        top_meal = OrderItem.objects.filter(order__created_at__date=today).values("menu_combination__name").annotate(total=S2("quantity")).order_by("-total").first()
    except: pass
    try:
        from landing.models import GalleryItem as GI
        gallery_items = GI.objects.all().order_by("-created_at")
    except:
        gallery_items = []
    menus = DailyMenu.objects.all().order_by("-date")[:7]
    try:
        today_menu = DailyMenu.objects.get(date=today)
    except: today_menu = None
    site = SiteSettings.get()
    riders = DishiUser.objects.filter(role="rider")
    all_staff = DishiUser.objects.filter(role__in=["kitchen","rider"]).order_by("role","name")
    pending_payments = Payment.objects.filter(status="PENDING").select_related("order__user").order_by("-created_at")
    all_payments = Payment.objects.all().select_related("order__user").order_by("-created_at")[:50]
    all_orders = Order.objects.filter(created_at__date=today).select_related("user","delivery_time_slot").prefetch_related("items__menu_combination").order_by("daily_order_number")
    delivery_slots = DeliverySlot.objects.all().order_by("order_position")
    ctx = {
        "orders_today": orders_today_qs.count(),
        "revenue_today": revenue_today,
        "orders_total": orders_total,
        "revenue_total": revenue_total,
        "completion_rate": completion_rate,
        "top_meal": top_meal,
        "menus": menus,
        "today_menu": today_menu,
        "site": site,
        "riders": riders,
        "today": today,
        "gallery_items": gallery_items,
        "all_staff": all_staff,
        "pending_payments": pending_payments,
        "all_payments": all_payments,
        "all_orders": all_orders,
        "delivery_slots": delivery_slots,
        "statuses": [("PAID","Paid"),("PREPARING","Preparing"),("DISPATCHED","Dispatched"),("DELIVERED","Delivered"),("CANCELLED","Cancelled"),("FAILED","Failed")],
    }
    return render(request, "owner/dashboard.html", ctx)


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

# ─── GALLERY ───
@owner_required
def add_gallery_owner(request):
    from django.contrib import messages
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            from landing.models import GalleryItem
            GalleryItem.objects.create(
                title=request.POST.get('title','Photo'),
                image=request.FILES['image'],
                category=request.POST.get('category','general'),
                uploaded_by=request.user,
            )
            messages.success(request, 'Photo added to gallery!')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('/owner/#tab-site')

@owner_required
def delete_gallery_owner(request, pk):
    from django.contrib import messages
    try:
        from landing.models import GalleryItem
        item = GalleryItem.objects.get(pk=pk)
        item.delete()
        messages.success(request, 'Photo deleted.')
    except Exception as e:
        messages.error(request, f'Error: {e}')
    return redirect('/owner/')

# ─── SLOT ───
@owner_required
def add_slot(request):
    from django.contrib import messages
    from delivery.models import DeliverySlot
    if request.method == 'POST':
        DeliverySlot.objects.create(
            label=request.POST.get('label',''),
            start_time=request.POST.get('start_time','12:00'),
            end_time=request.POST.get('end_time','12:30'),
            capacity=int(request.POST.get('capacity',30)),
        )
        messages.success(request, 'Slot added!')
    return redirect('/owner/')

# ─── RIDER ───
@owner_required
def add_rider(request):
    from django.contrib import messages
    from users.models import DishiUser
    if request.method == 'POST':
        phone = request.POST.get('phone','').strip()
        name = request.POST.get('name','').strip()
        if not DishiUser.objects.filter(phone_number=phone).exists():
            DishiUser.objects.create_user(
                phone_number=phone,
                password=phone,
                name=name,
                role='rider',
            )
            messages.success(request, f'Rider {name} added!')
        else:
            messages.error(request, 'Phone already registered.')
    return redirect('/owner/')

# ─── STAFF ───
@owner_required
def add_staff(request):
    from django.contrib import messages
    from users.models import DishiUser
    if request.method == 'POST':
        phone = request.POST.get('phone','').strip()
        name = request.POST.get('name','').strip()
        role = request.POST.get('role','kitchen')
        password = request.POST.get('password','staff123')
        if not DishiUser.objects.filter(phone_number=phone).exists():
            DishiUser.objects.create_user(
                phone_number=phone, password=password,
                name=name, role=role,
            )
            messages.success(request, f'{name} added as {role}!')
        else:
            messages.error(request, 'Phone already registered.')
    return redirect('/owner/')

# ─── COMBO TOGGLE ───
@owner_required
def toggle_combo(request, pk):
    from django.contrib import messages
    from menu.models import MenuCombination
    if request.method == 'POST':
        combo = get_object_or_404(MenuCombination, pk=pk)
        combo.is_available = not combo.is_available
        combo.save()
        messages.success(request, f'{"Available" if combo.is_available else "Hidden"}: {combo.name}')
    return redirect('/owner/')

@owner_required
def delete_combo(request, pk):
    from django.contrib import messages
    from menu.models import MenuCombination
    combo = get_object_or_404(MenuCombination, pk=pk)
    name = combo.name
    combo.delete()
    messages.success(request, f'Removed: {name}')
    return redirect('/owner/')

# ─── REJECT PAYMENT ───
@owner_required
def reject_payment(request, pk):
    from django.contrib import messages
    from payments.models import Payment
    payment = get_object_or_404(Payment, pk=pk)
    payment.status = 'FAILED'
    payment.save()
    messages.success(request, f'Payment rejected: {payment.mpesa_code}')
    return redirect('/owner/')
