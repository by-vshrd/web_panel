from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Публичные страницы
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('faq/', views.faq, name='faq'),

    # Личный кабинет
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create-profile/', views.create_profile, name='create_profile'),
    path('qr/<int:profile_id>/', views.qr_code, name='qr_code'),
    path('link/<int:profile_id>/', views.subscription_link, name='subscription_link'),
    path('activation-code/', views.get_activation_code, name='activation_code'),

    # Статус сервера
    path('server-status/', views.server_status, name='server_status'),

    # Административные функции
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage-user/<int:user_id>/', views.manage_user, name='manage_user'),
    path('delete-profile/<int:profile_id>/', views.delete_profile, name='delete_profile'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('manual-extend/<int:user_id>/', views.manual_extend, name='manual_extend'),
    path('admin-settings/', views.admin_settings, name='admin_settings'),
    path('sync-profile-sub-id/<int:profile_id>/', views.sync_profile_sub_id, name='sync_profile_sub_id'),

    #страница оплаты
    path('payment/', views.payment_page, name='payment_page'),
    path('payment/', views.payment_page, name='payment_page'),
    path('submit-payment/', views.submit_payment, name='submit_payment'),
    path('admin/payments/', views.admin_payments, name='admin_payments'),
    path('admin/payments/<int:ticket_id>/approve/', views.approve_payment, name='approve_payment'),
    path('admin/payments/<int:ticket_id>/reject/', views.reject_payment, name='reject_payment'),

    #уведомления
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/create/', views.notification_create, name='notification_create'),
    path('notifications/delete/<int:notification_id>/', views.notification_delete, name='notification_delete'),
    path('notifications/toggle/<int:notification_id>/', views.notification_toggle, name='notification_toggle'),
]