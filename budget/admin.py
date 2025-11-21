from django.contrib import admin
from .models import UserProfile, Category, Payment, Transaction, MonthlyBudget

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'birth_date', 'age', 'phone_number']
    list_filter = ['birth_date']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    readonly_fields = ['age']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'amount', 'due_date', 'category_type', 'is_active', 'is_monthly']
    list_filter = ['category_type', 'is_active', 'is_monthly', 'due_date']
    search_fields = ['name', 'user__username']
    list_editable = ['is_active', 'is_monthly']
    date_hierarchy = 'due_date'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['category', 'amount_paid', 'payment_date', 'status', 'created_at']
    list_filter = ['status', 'payment_date', 'category__category_type']
    search_fields = ['category__name', 'notes']
    date_hierarchy = 'payment_date'
    list_editable = ['status']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'amount', 'transaction_type', 'category', 'date']
    list_filter = ['transaction_type', 'date', 'category__category_type']
    search_fields = ['title', 'description', 'user__username']
    date_hierarchy = 'date'
    list_editable = ['transaction_type']

@admin.register(MonthlyBudget)
class MonthlyBudgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'month', 'total_budget', 'total_expenses', 'remaining_budget']
    list_filter = ['month']
    search_fields = ['user__username']
    date_hierarchy = 'month'
    readonly_fields = ['total_expenses', 'remaining_budget']
