from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"
    
    @property
    def age(self):
        if self.birth_date:
            today = timezone.now().date()
            return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return None

class Category(models.Model):
    CATEGORY_CHOICES = [
        ('rent', 'Rent'),
        ('internet', 'Internet'),
        ('water', 'Water'),
        ('electricity', 'Electricity'),
        ('shopping', 'Shopping'),
        ('food', 'Food'),
        ('transportation', 'Transportation'),
        ('entertainment', 'Entertainment'),
        ('health', 'Health'),
        ('education', 'Education'),
        ('other', 'Other'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    is_active = models.BooleanField(default=True)
    is_monthly = models.BooleanField(default=True, help_text="Automatically renew every month")
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_date = models.DateField(null=True, blank=True, help_text="Date when payment was made")
    gcash_number = models.CharField(max_length=15, blank=True, help_text="GCash account number for payments")
    category_id = models.CharField(max_length=50, blank=True, help_text="Category ID for identification")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"
    
    @property
    def is_due_soon(self):
        today = timezone.now().date()
        days_until_due = (self.due_date - today).days
        return 0 <= days_until_due <= 2
    
    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date()
    
    def get_next_due_date(self):
        """Get the next due date for monthly categories"""
        if self.is_monthly:
            current_due = self.due_date
            today = timezone.now().date()
            
            # If current due date has passed, calculate next month's due date
            if current_due < today:
                if current_due.month == 12:
                    next_due = current_due.replace(year=current_due.year + 1, month=1)
                else:
                    next_due = current_due.replace(month=current_due.month + 1)
                return next_due
            return current_due
        return self.due_date
    
    def mark_as_paid(self):
        """Mark category as paid without changing the due date"""
        from django.utils import timezone
        
        self.payment_status = 'paid'
        self.payment_date = timezone.now().date()
        self.save()
    
    def reset_for_new_month(self):
        """Reset payment status for monthly categories when month changes"""
        from django.utils import timezone
        import calendar
        
        today = timezone.now().date()
        
        # Check if we're in a new month and the category is monthly and paid
        if (self.is_monthly and 
            self.payment_status == 'paid' and 
            self.payment_date and 
            self.payment_date.month != today.month):
            
            # Calculate next due date (same day next month)
            current_due = self.due_date
            
            # Calculate next month and year
            if current_due.month == 12:
                next_month = 1
                next_year = current_due.year + 1
            else:
                next_month = current_due.month + 1
                next_year = current_due.year
            
            # Handle day overflow (e.g., January 31 -> February 28/29)
            try:
                # Try to create the date with the same day
                new_due = current_due.replace(year=next_year, month=next_month)
            except ValueError:
                # Day is out of range for the month, use the last day of the month
                last_day = calendar.monthrange(next_year, next_month)[1]
                new_due = current_due.replace(year=next_year, month=next_month, day=last_day)
            
            # Reset to unpaid for the new month with updated due date
            self.payment_status = 'unpaid'
            self.payment_date = None
            self.due_date = new_due
            self.save()
            return True
        
        return False

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('gcash', 'GCash'),
        ('cash', 'Cash'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('full', 'Full Payment'),
        ('partial', 'Partial Payment'),
    ]
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default='full')
    transaction_id = models.CharField(max_length=100, blank=True)
    gcash_account_used = models.CharField(max_length=20, blank=True)
    proof_image = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.category.name} - {self.amount_paid} - {self.payment_date}"

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.amount} - {self.date}"

class MonthlyBudget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    month = models.DateField()  # Store as first day of month
    total_budget = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'month']
    
    def __str__(self):
        return f"{self.user.username} - {self.month.strftime('%B %Y')}"
    
    @property
    def total_expenses(self):
        start_date = self.month.replace(day=1)
        if self.month.month == 12:
            end_date = self.month.replace(year=self.month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = self.month.replace(month=self.month.month + 1, day=1) - timedelta(days=1)
        
        expenses = Transaction.objects.filter(
            user=self.user,
            transaction_type='expense',
            date__range=[start_date, end_date]
        )
        return sum(expense.amount for expense in expenses)
    
    @property
    def remaining_budget(self):
        return self.total_budget - self.total_expenses

class BudgetHistory(models.Model):
    """Track individual budget additions for a month"""
    budget = models.ForeignKey(MonthlyBudget, on_delete=models.CASCADE, related_name='history')
    amount_added = models.DecimalField(max_digits=10, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Optional notes for this budget addition")
    
    class Meta:
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.budget.user.username} - {self.amount_added} on {self.added_at.strftime('%Y-%m-%d')}"