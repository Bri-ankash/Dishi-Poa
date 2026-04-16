from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import DishiUser

def login_view(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, phone_number=phone, password=password)
        if user:
            login(request, user)
            if user.role == 'kitchen': return redirect('/kitchen/')
            if user.role == 'owner': return redirect('/owner/')
            return redirect('/dashboard/')
        messages.error(request, 'Invalid phone number or password.')
    return render(request, 'auth/login.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()
        name = request.POST.get('name', '').strip()
        if DishiUser.objects.filter(phone_number=phone).exists():
            messages.error(request, 'Phone number already registered. Please login.')
            return redirect('/login/')
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        else:
            user = DishiUser.objects.create_user(phone_number=phone, password=password, name=name, role='customer')
            login(request, user)
            messages.success(request, f'Welcome, {name or phone}!')
            return redirect('/dashboard/')
    return render(request, 'auth/register.html')

def logout_view(request):
    logout(request)
    return redirect('/')
