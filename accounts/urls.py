from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Публичные страницы
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Личный кабинет
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create-profile/', views.create_profile, name='create_profile'),
    path('qr/<str:protocol>/', views.qr_code, name='qr_code'),
    path('link/<str:protocol>/', views.subscription_link, name='subscription_link'),

    # Статус сервера
    path('server-status/', views.server_status, name='server_status'),

    # Административные функции
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage-user/<int:user_id>/', views.manage_user, name='manage_user'),
    path('delete-profile/<int:profile_id>/', views.delete_profile, name='delete_profile'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('admin-settings/', views.admin_settings, name='admin_settings'),
    path('sync-profile-sub-id/<int:profile_id>/', views.sync_profile_sub_id, name='sync_profile_sub_id'),
]