from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from .models import Order, OrderItem, generate_order_code
from menu.models import DailyMenu, MenuCombination
from delivery.models import DeliverySlot
from users.models import SavedLocation
from core.models import SiteSettings
from payments.models import Payment

@login_required(login_url='/login/')
def dashboard(request):
    user = request.user
    today = timezone.localdate()
    try:
        menu = DailyMenu.objects.prefetch_related('combinations').get(date=today, is_active=True)
    except DailyMenu.DoesNotExist:
        menu = None

    slots = DeliverySlot.objects.filter(is_active=True)
    locations = SavedLocation.objects.filter(user=user)
    orders = Order.objects.filter(user=user).order_by('-created_at')[:10]
    today_order = Order.objects.filter(
        user=user, created_at__date=today
    ).exclude(status='CANCELLED').first()
    site = SiteSettings.get()

    ctx = {
        'menu': menu,
        'slots': slots,
        'locations': locations,
        'orders': orders,
        'today_order': today_order,
        'site': site,
        'today': today,
    }
    return render(request, 'dashboard/customer.html', ctx)

@login_required(login_url='/login/')
@transaction.atomic
def place_order(request):
    if request.method != 'POST':
        return redirect('/dashboard/')

    user = request.user
    today = timezone.localdate()
    site = SiteSettings.get()

    try:
        menu = DailyMenu.objects.get(date=today, is_active=True)
    except DailyMenu.DoesNotExist:
        messages.error(request, 'No menu available today.')
        return redirect('/dashboard/')

    if not menu.is_ordering_open:
        messages.error(request, f'Sorry, ordering is closed. Cutoff was {menu.cutoff_time.strftime("%H:%M")}.')
        return redirect('/dashboard/')

    # Check one order per day
    existing = Order.objects.filter(
        user=user, created_at__date=today
    ).exclude(status__in=['CANCELLED','FAILED']).first()
    if existing:
        messages.warning(request, f'You already have an order today: {existing.order_code}')
        return redirect('/dashboard/')

    # Get items from form
    items = []
    total = 0
    for key, val in request.POST.items():
        if key.startswith('qty_') and int(val) > 0:
            combo_id = int(key.split('_')[1])
            qty = int(val)
            try:
                combo = MenuCombination.objects.select_for_update().get(id=combo_id, daily_menu=menu, is_available=True)
                if combo.remaining < qty:
                    messages.error(request, f'Only {combo.remaining} plates of {combo.name} left!')
                    return redirect('/dashboard/')
                items.append((combo, qty))
                total += combo.price * qty
            except MenuCombination.DoesNotExist:
                pass

    if not items:
        messages.error(request, 'Please select at least one item.')
        return redirect('/dashboard/')

    # Delivery
    slot_id = request.POST.get('slot_id')
    location_id = request.POST.get('location_id')
    address_text = request.POST.get('address_text', '')
    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')

    slot = None
    if slot_id:
        try:
            slot = DeliverySlot.objects.get(id=slot_id, is_active=True)
            if slot.is_full:
                messages.error(request, f'Slot {slot.label} is fully booked. Choose another.')
                return redirect('/dashboard/')
        except DeliverySlot.DoesNotExist:
            pass

    location = None
    if location_id:
        try:
            location = SavedLocation.objects.get(id=location_id, user=user)
            address_text = location.address_text
            latitude = location.latitude
            longitude = location.longitude
        except SavedLocation.DoesNotExist:
            pass

    # Create order
    order = Order.objects.create(
        user=user,
        order_code='',  # auto-generated in save()
        daily_order_number=0,
        status='PENDING',
        delivery_location=location,
        delivery_address_text=address_text,
        delivery_latitude=float(latitude) if latitude else None,
        delivery_longitude=float(longitude) if longitude else None,
        delivery_time_slot=slot,
        total_amount=total,
        special_instructions=request.POST.get('instructions', ''),
    )

    for combo, qty in items:
        OrderItem.objects.create(order=order, menu_combination=combo, quantity=qty, unit_price=combo.price, subtotal=combo.price*qty)

    messages.success(request, f'Order {order.order_code} placed! Please pay within 30 minutes.')
    return redirect(f'/order/{order.order_code}/pay/')

@login_required(login_url='/login/')
def order_pay(request, code):
    order = get_object_or_404(Order, order_code=code, user=request.user)
    site = SiteSettings.get()
    if order.status not in ['PENDING']:
        return redirect(f'/order/{code}/')
    return render(request, 'dashboard/pay.html', {'order': order, 'site': site})

@login_required(login_url='/login/')
def submit_mpesa_code(request, code):
    if request.method != 'POST': return redirect(f'/order/{code}/pay/')
    order = get_object_or_404(Order, order_code=code, user=request.user)
    mpesa_code = request.POST.get('mpesa_code', '').strip().upper()
    mpesa_phone = request.POST.get('mpesa_phone', '').strip()

    if not mpesa_code or len(mpesa_code) < 8:
        messages.error(request, 'Enter a valid M-Pesa code.')
        return redirect(f'/order/{code}/pay/')

    if Payment.objects.filter(mpesa_code=mpesa_code).exists():
        messages.error(request, 'That M-Pesa code has already been used.')
        return redirect(f'/order/{code}/pay/')

    Payment.objects.create(
        order=order, amount=order.total_amount,
        mpesa_code=mpesa_code, mpesa_phone=mpesa_phone, status='PENDING'
    )
    messages.success(request, 'M-Pesa code submitted! We are confirming your payment.')
    return redirect(f'/order/{code}/')

@login_required(login_url='/login/')
def order_detail(request, code):
    order = get_object_or_404(Order, order_code=code, user=request.user)
    site = SiteSettings.get()
    return render(request, 'dashboard/order_detail.html', {'order': order, 'site': site})

@login_required(login_url='/login/')
def edit_order(request, code):
    order = get_object_or_404(Order, order_code=code, user=request.user)
    if not order.can_edit:
        messages.error(request, 'Order can no longer be edited (10-minute window passed).')
        return redirect(f'/order/{code}/')
    if request.method == 'POST':
        # Allow updating delivery address and instructions only
        order.delivery_address_text = request.POST.get('delivery_address_text', order.delivery_address_text)
        order.special_instructions = request.POST.get('special_instructions', order.special_instructions)
        slot_id = request.POST.get('slot_id')
        if slot_id:
            try:
                order.delivery_time_slot = DeliverySlot.objects.get(id=slot_id)
            except: pass
        order.save()
        messages.success(request, 'Order updated!')
        return redirect(f'/order/{code}/')
    site = SiteSettings.get()
    slots = DeliverySlot.objects.filter(is_active=True)
    return render(request, 'dashboard/edit_order.html', {'order': order, 'slots': slots, 'site': site})

@login_required(login_url='/login/')
def save_location(request):
    if request.method == 'POST':
        SavedLocation.objects.create(
            user=request.user,
            name=request.POST.get('name', 'Location'),
            address_text=request.POST.get('address_text', ''),
            latitude=request.POST.get('latitude') or None,
            longitude=request.POST.get('longitude') or None,
        )
        messages.success(request, 'Location saved!')
    return redirect('/dashboard/')
