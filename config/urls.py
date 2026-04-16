from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from core import kitchen_views
from users import views as user_views
from orders import views as order_views
from payments import views as payment_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Landing
    path('', core_views.landing, name='landing'),
    # Auth
    path('login/', user_views.login_view, name='login'),
    path('register/', user_views.register_view, name='register'),
    path('logout/', user_views.logout_view, name='logout'),
    # Customer
    path('dashboard/', order_views.dashboard, name='dashboard'),
    path('order/place/', order_views.place_order, name='place_order'),
    path('order/<str:code>/', order_views.order_detail, name='order_detail'),
    path('order/<str:code>/pay/', order_views.order_pay, name='order_pay'),
    path('order/<str:code>/pay/submit/', order_views.submit_mpesa_code, name='submit_mpesa'),
    path('order/<str:code>/edit/', order_views.edit_order, name='edit_order'),
    path('location/save/', order_views.save_location, name='save_location'),
    # Kitchen
    path('kitchen/', kitchen_views.kitchen_dashboard, name='kitchen'),
    path('kitchen/payment/<int:payment_id>/confirm/', kitchen_views.confirm_payment, name='confirm_payment'),
    path('kitchen/order/<int:order_id>/status/', kitchen_views.update_order_status, name='update_status'),
    # Owner
    path('owner/', kitchen_views.owner_dashboard, name='owner'),
    path('owner/menu/create/', kitchen_views.create_menu, name='create_menu'),
    path('owner/menu/<int:menu_id>/combo/', kitchen_views.add_combination, name='add_combination'),
    path('owner/settings/', kitchen_views.update_site_settings, name='site_settings'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
