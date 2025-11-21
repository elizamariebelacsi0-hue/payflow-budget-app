from django.urls import path
from . import views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('home/', views.home, name='home'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    path('category/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    path('category/<int:category_id>/toggle-payment/', views.toggle_payment_status, name='toggle_payment_status'),
    path('add-category/', views.add_category, name='add_category'),
    path('transactions/', views.transactions, name='transactions'),
    path('profile/', views.profile, name='profile'),
    path('help/', views.help_page, name='help'),
    path('about/', views.about, name='about'),
    path('logo/', views.logo_page, name='logo_page'),
    path('poster/', views.poster_page, name='poster_page'),
    path('advertisement/', views.advertisement_page, name='advertisement_page'),
    path('close-account/', views.close_account, name='close_account'),
    path('toggle-dashboard/', views.toggle_dashboard, name='toggle_dashboard'),
    path('update-budget/', views.update_budget, name='update_budget'),
    path('monthly-overview/', views.monthly_overview, name='monthly_overview'),
    path('month-transactions/<str:month_key>/', views.month_transactions, name='month_transactions'),
    path('unpaid-bills/<int:month>/', views.unpaid_bills, name='unpaid_bills'),
    path('search-suggestions/', views.search_suggestions, name='search_suggestions'),
    path('search/', views.search_results, name='search_results'),
    path('admin-search-suggestions/', views.admin_search_suggestions, name='admin_search_suggestions'),
    # SEO and Google verification
    path('google2a6ee76082d4d9c7.html', views.google_verification, name='google_verification'),
    path('sitemap.xml', views.sitemap, name='sitemap'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    # Removed legacy GCash payment routes in favor of unified Record Payment modal
] 

