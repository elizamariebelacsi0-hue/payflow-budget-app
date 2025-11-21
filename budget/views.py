from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Q
from django.db import models
from datetime import datetime, timedelta
from calendar import month_name
from functools import wraps
from .models import UserProfile, Category, Payment, Transaction, MonthlyBudget, BudgetHistory
from .forms import UserRegistrationForm, UserProfileForm, CategoryForm, CategoryEditForm, PaymentForm, MonthlyBudgetForm, AdditionalBudgetForm


def redirect_staff_to_admin(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('admin_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def welcome(request):
    return render(request, 'budget/welcome.html')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = form.cleaned_data.get('role', 'user')
            user.is_staff = role == 'admin'
            user.save()
            # Get phone number from the form data
            phone_number = request.POST.get('phone', '')
            # Create UserProfile with phone number
            UserProfile.objects.create(user=user, phone_number=phone_number)
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('home')
        else:
            # Handle form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    return render(request, 'budget/register.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        selected_role = request.POST.get('role', 'user')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if selected_role == 'admin' and not user.is_staff:
                messages.error(request, 'You selected Admin but your account is not authorized as admin.')
                return redirect('login')
            if selected_role == 'user' and user.is_staff:
                messages.error(request, 'Please select Admin to access your admin account.')
                return redirect('login')
            login(request, user)
            messages.success(request, 'Welcome back!')
            return redirect('admin_dashboard' if user.is_staff else 'home')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'budget/login.html')

@login_required
@redirect_staff_to_admin
def home(request):
    # Get user's categories
    categories = Category.objects.filter(user=request.user, is_active=True)
    
    # Reset monthly categories if month has changed
    for category in categories:
        if category.is_monthly:
            category.reset_for_new_month()
    
    # Get current month's budget
    current_month = timezone.now().date().replace(day=1)
    monthly_budget, created = MonthlyBudget.objects.get_or_create(
        user=request.user,
        month=current_month,
        defaults={'total_budget': 0}
    )
    
    # Get total expenses for current month
    start_date = current_month
    if current_month.month == 12:
        end_date = current_month.replace(year=current_month.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_date = current_month.replace(month=current_month.month + 1, day=1) - timedelta(days=1)
    
    total_expenses = Transaction.objects.filter(
        user=request.user,
        transaction_type='expense',
        date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Refresh categories after potential reset
    categories = Category.objects.filter(user=request.user, is_active=True)
    
    # Get due soon categories (unpaid only)
    due_soon_categories = categories.filter(is_active=True, payment_status='unpaid')
    due_soon = []
    for category in due_soon_categories:
        if category.is_due_soon or category.is_overdue:
            due_soon.append(category)
    
    context = {
        'categories': categories,
        'monthly_budget': monthly_budget,
        'total_expenses': total_expenses,
        'due_soon': due_soon,
        'now': timezone.now().date(),
    }
    return render(request, 'budget/home.html', context)


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'budget/admin_dashboard.html', {'users': users})

@login_required
@redirect_staff_to_admin
def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    payments = Payment.objects.filter(category=category).order_by('-payment_date')
    
    # Reset monthly category if month has changed
    if category.is_monthly:
        category.reset_for_new_month()
    
    if request.method == 'POST':
        # Check if this is a category edit or payment record
        if 'edit_category' in request.POST:
            form = CategoryEditForm(request.POST, instance=category)
            if form.is_valid():
                form.save()
                messages.success(request, 'Category updated successfully!')
                return redirect('category_detail', category_id=category.id)
        elif 'record_payment' in request.POST:
            payment_form = PaymentForm(request.POST, request.FILES, category=category)
            if payment_form.is_valid():
                payment = payment_form.save(commit=False)
                payment.category = category
                payment.status = 'paid'
                
                # Validate partial payment amount
                if payment.payment_type == 'partial' and payment.amount_paid >= category.amount:
                    messages.error(request, 'PAYMENT_ERROR')
                    form = CategoryEditForm(instance=category)
                    payment_form = PaymentForm(category=category)
                    context = {
                        'category': category,
                        'payments': payments,
                        'form': form,
                        'payment_form': payment_form,
                    }
                    return render(request, 'budget/category_detail.html', context)

                # Budget check: ensure sufficient remaining monthly budget
                current_month = timezone.now().replace(day=1)
                try:
                    monthly_budget = MonthlyBudget.objects.get(user=request.user, month=current_month)
                    remaining_budget = monthly_budget.remaining_budget
                except MonthlyBudget.DoesNotExist:
                    remaining_budget = 0
                if payment.amount_paid > remaining_budget:
                    messages.error(request, 'Not enough balance in your monthly budget to process this payment.')
                    return redirect('home')
                payment.save()
                
                # Handle full vs partial payment
                if payment.payment_type == 'full':
                    # Mark category as paid
                    category.mark_as_paid()
                    messages.success(request, 'PAYMENT_SUCCESS')
                else:
                    # Partial payment - reduce category amount but keep due date
                    category.amount -= payment.amount_paid
                    category.save()
                    messages.success(request, 'PAYMENT_SUCCESS')
                
                # Create transaction record
                payment_label = 'Full Payment' if payment.payment_type == 'full' else 'Partial Payment'
                if payment.payment_method == 'gcash':
                    tx_description = (
                        f"{payment_label} - The payment was processed through GCash (Account No. {payment.gcash_account_used}) "
                        f"under transaction number {payment.transaction_id}."
                    )
                else:
                    tx_description = f"{payment_label} - The payment was processed through cash."
                
                Transaction.objects.create(
                    user=request.user,
                    title=f"{payment_label} for {category.name}",
                    amount=payment.amount_paid,
                    transaction_type='expense',
                    category=category,
                    date=payment.payment_date,
                    description=tx_description
                )
                
                return redirect('category_detail', category_id=category.id)
    else:
        form = CategoryEditForm(instance=category)
        payment_form = PaymentForm(category=category)
    
    context = {
        'category': category,
        'payments': payments,
        'form': form,
        'payment_form': payment_form,
    }
    return render(request, 'budget/category_detail.html', context)

@login_required
@redirect_staff_to_admin
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, 'Category added successfully!')
            return redirect('home')
        else:
            # Handle form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    return redirect('home')

@login_required
@redirect_staff_to_admin
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    if request.method == 'POST':
        # Delete related transactions first
        Transaction.objects.filter(category=category).delete()
        # Delete related payments
        Payment.objects.filter(category=category).delete()
        # Delete the category
        category.delete()
        messages.success(request, 'Category and all related data deleted successfully!')
        return redirect('home')
    return render(request, 'budget/delete_category.html', {'category': category})

@login_required
@redirect_staff_to_admin
def transactions(request):
    transactions_list = Transaction.objects.filter(user=request.user).order_by('-date')
    
    context = {
        'transactions': transactions_list,
    }
    return render(request, 'budget/transactions.html', context)

@login_required
def profile(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            # Check if username is unique (excluding current user)
            new_username = form.cleaned_data['username']
            if User.objects.filter(username=new_username).exclude(id=request.user.id).exists():
                messages.error(request, 'Username already exists. Please choose a different username.')
            else:
                form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
        else:
            # Handle form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UserProfileForm(instance=profile)
    
    context = {
        'profile': profile,
        'form': form,
        'base_template': 'budget/admin_base.html' if request.user.is_staff else 'budget/base.html',
    }
    return render(request, 'budget/profile.html', context)

@login_required
@redirect_staff_to_admin
def help_page(request):
    return render(request, 'budget/help.html')

@login_required
def about(request):
    return render(request, 'budget/about.html')

@login_required
def logo_page(request):
    return render(request, 'budget/logo_page.html')

@login_required
def poster_page(request):
    return render(request, 'budget/poster_page.html')

@login_required
def advertisement_page(request):
    return render(request, 'budget/advertisement_page.html')

@login_required
def close_account(request):
    if request.method == 'POST':
        user = request.user
        username = user.username  # Store username for confirmation message
        
        # Delete all user data in the correct order to avoid foreign key constraints
        # 1. Delete all transactions
        Transaction.objects.filter(user=user).delete()
        
        # 2. Delete all payments (related to categories)
        Payment.objects.filter(category__user=user).delete()
        
        # 3. Delete all categories
        Category.objects.filter(user=user).delete()
        
        # 4. Delete all monthly budgets
        MonthlyBudget.objects.filter(user=user).delete()
        
        # 5. Delete user profile
        UserProfile.objects.filter(user=user).delete()
        
        # 6. Finally, delete the user account itself
        user.delete()
        
        messages.success(request, f'Account "{username}" has been permanently deleted.')
        return redirect('login')
    
    # Use different template for admin users
    template = 'budget/admin_close_account.html' if request.user.is_staff else 'budget/close_account.html'
    return render(request, template)

@login_required
@redirect_staff_to_admin
def toggle_dashboard(request):
    if request.method == 'POST':
        # This would typically be stored in user preferences or session
        # For now, we'll just return a success response
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})

@login_required
@redirect_staff_to_admin
def toggle_payment_status(request, category_id):
    """Toggle payment status of a category"""
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id, user=request.user)
        
        if category.payment_status == 'unpaid':
            # Budget check for instant paid action
            current_month = timezone.now().replace(day=1)
            try:
                monthly_budget = MonthlyBudget.objects.get(user=request.user, month=current_month)
                remaining_budget = monthly_budget.remaining_budget
            except MonthlyBudget.DoesNotExist:
                remaining_budget = 0
            if category.amount > remaining_budget:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Not enough balance in your monthly budget to process this payment.'
                })
            # Mark as paid
            category.mark_as_paid()
            
            # Create transaction record
            Transaction.objects.create(
                user=request.user,
                title=f"Payment for {category.name}",
                amount=category.amount,
                transaction_type='expense',
                category=category,
                date=category.payment_date,
                description="The payment was processed through cash"
            )
            
            return JsonResponse({
                'status': 'success',
                'new_status': 'paid',
                'message': f'{category.name} marked as paid!'
            })
        else:
            # Mark as unpaid
            category.payment_status = 'unpaid'
            category.payment_date = None
            category.save()
            return JsonResponse({
                'status': 'success',
                'new_status': 'unpaid',
                'message': f'{category.name} marked as unpaid!'
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
@redirect_staff_to_admin
def monthly_overview(request):
    """API endpoint to get monthly overview data for the last 12 months"""
    from datetime import datetime, timedelta
    from calendar import month_name
    
    months = []
    
    # Get the last 12 months
    current_date = timezone.now().date()
    for i in range(12):
        # Calculate month date (first day of the month)
        if current_date.month - i <= 0:
            month_date = current_date.replace(year=current_date.year - 1, month=12 + (current_date.month - i), day=1)
        else:
            month_date = current_date.replace(month=current_date.month - i, day=1)
        
        # Get budget for this month
        try:
            budget = MonthlyBudget.objects.get(user=request.user, month=month_date)
            budget_amount = budget.total_budget
        except MonthlyBudget.DoesNotExist:
            budget_amount = 0
        
        # Get expenses for this month
        if month_date.month == 12:
            end_date = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
        
        expenses = Transaction.objects.filter(
            user=request.user,
            transaction_type='expense',
            date__range=[month_date, end_date]
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Get transaction count for this month
        transaction_count = Transaction.objects.filter(
            user=request.user,
            date__range=[month_date, end_date]
        ).count()
        
        months.append({
            'month_key': f"{month_date.year}-{month_date.month:02d}",
            'month_name': month_name[month_date.month] + ' ' + str(month_date.year),
            'budget': float(budget_amount),
            'expenses': float(expenses),
            'transaction_count': transaction_count
        })
    
    return JsonResponse({'months': months})

@login_required
@redirect_staff_to_admin
def month_transactions(request, month_key):
    """API endpoint to get transactions for a specific month"""
    from datetime import datetime, timedelta
    from calendar import month_name
    
    try:
        year, month = month_key.split('-')
        year, month = int(year), int(month)
        
        # Calculate month date range
        month_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
        
        # Get budget for this month
        try:
            budget = MonthlyBudget.objects.get(user=request.user, month=month_date)
            budget_amount = budget.total_budget
            
            # Get budget history for this month
            budget_history = BudgetHistory.objects.filter(budget=budget).order_by('-added_at')
            history_data = []
            for entry in budget_history:
                history_data.append({
                    'amount': float(entry.amount_added),
                    'date': entry.added_at.strftime('%B %d, %Y %I:%M %p'),
                    'notes': entry.notes or 'No notes'
                })
        except MonthlyBudget.DoesNotExist:
            budget_amount = 0
            history_data = []
        
        # Get expenses for this month
        expenses = Transaction.objects.filter(
            user=request.user,
            transaction_type='expense',
            date__range=[month_date, end_date]
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Get all transactions for this month
        transactions = Transaction.objects.filter(
            user=request.user,
            date__range=[month_date, end_date]
        ).order_by('-date')
        
        transactions_data = []
        for transaction in transactions:
            transactions_data.append({
                'title': transaction.title,
                'amount': float(transaction.amount),
                'transaction_type': transaction.transaction_type,
                'date': transaction.date.strftime('%B %d, %Y'),
                'category': transaction.category.name if transaction.category else None,
                'description': transaction.description
            })
        
        return JsonResponse({
            'month_name': month_name[month] + ' ' + str(year),
            'budget': float(budget_amount),
            'expenses': float(expenses),
            'transactions': transactions_data,
            'budget_history': history_data
        })
        
    except (ValueError, IndexError):
        return JsonResponse({'error': 'Invalid month format'}, status=400)

@login_required
@redirect_staff_to_admin
def update_budget(request):
    # Get month and year from URL parameters, default to current month
    month_param = request.GET.get('month')
    year_param = request.GET.get('year')
    
    if month_param and year_param:
        try:
            target_month = int(month_param)
            target_year = int(year_param)
            current_month = timezone.now().replace(year=target_year, month=target_month, day=1)
        except (ValueError, TypeError):
            current_month = timezone.now().replace(day=1)
    else:
        current_month = timezone.now().replace(day=1)
    
    if request.method == 'POST':
        # Check if this is an additional budget or initial budget update
        if 'add_additional_budget' in request.POST:
            additional_form = AdditionalBudgetForm(request.POST)
            if additional_form.is_valid():
                # Get or create budget for current month
                budget, created = MonthlyBudget.objects.get_or_create(
                    user=request.user,
                    month=current_month,
                    defaults={'total_budget': 0}
                )
                
                # Add the additional amount to existing budget
                additional_amount = additional_form.cleaned_data['amount_added']
                budget.total_budget += additional_amount
                budget.save()
                
                # Create budget history entry
                BudgetHistory.objects.create(
                    budget=budget,
                    amount_added=additional_amount,
                    notes=additional_form.cleaned_data.get('notes', '')
                )
                
                messages.success(request, f'Additional budget of ₱{additional_amount:,.2f} added successfully!')
                return redirect('home')
        else:
            # Regular budget update (set initial budget)
            form = MonthlyBudgetForm(request.POST)
            if form.is_valid():
                # Get or create budget for current month
                budget, created = MonthlyBudget.objects.get_or_create(
                    user=request.user,
                    month=current_month,
                    defaults={'total_budget': 0}
                )
                
                # Calculate the difference
                old_budget = budget.total_budget
                new_budget = form.cleaned_data['total_budget']
                
                # If setting a new initial budget and there's no history, or if adding budget
                if created or budget.total_budget == 0:
                    # Set initial budget
                    budget.total_budget = new_budget
                    budget.save()
                    
                    # Record in history
                    BudgetHistory.objects.create(
                        budget=budget,
                        amount_added=new_budget,
                        notes='Initial budget'
                    )
                    messages.success(request, 'Budget set successfully!')
                else:
                    # If changing existing budget, calculate difference and add as history
                    difference = new_budget - old_budget
                    if difference > 0:
                        budget.total_budget = new_budget
                        budget.save()
                        
                        BudgetHistory.objects.create(
                            budget=budget,
                            amount_added=difference,
                            notes='Budget update'
                        )
                        messages.success(request, f'Budget updated! Added ₱{difference:,.2f} to your budget.')
                    elif difference < 0:
                        messages.error(request, 'Cannot reduce budget. Use "Additional Budget" to add more.')
                    else:
                        messages.info(request, 'Budget unchanged.')
                
                return redirect('home')
    else:
        # GET request - show forms
        try:
            existing_budget = MonthlyBudget.objects.get(user=request.user, month=current_month)
            form = MonthlyBudgetForm(instance=existing_budget)
        except MonthlyBudget.DoesNotExist:
            form = MonthlyBudgetForm()
        
        additional_form = AdditionalBudgetForm()
    
    return render(request, 'budget/update_budget.html', {
        'form': form,
        'additional_form': additional_form,
        'current_budget': MonthlyBudget.objects.filter(user=request.user, month=current_month).first()
    })

@login_required
@redirect_staff_to_admin
def payment_page(request, category_id):
    # Legacy route removed; redirect to category_detail
    return redirect('category_detail', category_id=category_id)

@login_required
@redirect_staff_to_admin
def process_gcash_payment(request, category_id):
    # Legacy route removed; redirect to category_detail
    return redirect('category_detail', category_id=category_id)

@login_required
@redirect_staff_to_admin
def unpaid_bills(request, month):
    """API endpoint to get unpaid bills for a specific month"""
    from calendar import month_name
    
    try:
        month_num = int(month)
        if month_num < 1 or month_num > 12:
            return JsonResponse({'error': 'Invalid month'}, status=400)
        
        current_year = timezone.now().year
        
        # Get all unpaid categories that are due soon or overdue
        categories = Category.objects.filter(
            user=request.user, 
            is_active=True, 
            payment_status='unpaid',
            due_date__month=month_num,
            due_date__year=current_year
        )
        
        unpaid_categories = []
        for category in categories:
            # Include categories that are due soon or overdue
            if category.is_due_soon or category.is_overdue:
                status = 'overdue' if category.is_overdue else 'due_soon'
                unpaid_categories.append({
                    'id': category.id,
                    'name': category.name,
                    'amount': float(category.amount),
                    'due_date': category.due_date.strftime('%B %d, %Y'),
                    'category_type': category.get_category_type_display(),
                    'is_monthly': category.is_monthly,
                    'status': status
                })
        
        return JsonResponse({
            'month_name': month_name[month_num],
            'unpaid_bills': unpaid_categories
        })
        
    except ValueError:
        return JsonResponse({'error': 'Invalid month format'}, status=400)

@login_required
@redirect_staff_to_admin
def search_suggestions(request):
    """API endpoint for search suggestions"""
    query = request.GET.get('q', '').strip().lower()
    if not query:
        return JsonResponse({'results': []})
    
    results = []
    
    # Search categories
    categories = Category.objects.filter(
        user=request.user, 
        is_active=True
    ).filter(
        Q(name__icontains=query) | 
        Q(category_type__icontains=query)
    )[:5]
    
    for category in categories:
        results.append({
            'name': category.name,
            'type': 'Category',
            'icon': 'fas fa-tag',
            'url': f'/category/{category.id}/',
            'details': f'₱{category.amount} - {category.get_category_type_display()}'
        })
    
    # Search transactions
    transactions = Transaction.objects.filter(
        user=request.user
    ).filter(
        Q(title__icontains=query) |
        Q(description__icontains=query)
    )[:5]
    
    for transaction in transactions:
        results.append({
            'name': transaction.title,
            'type': 'Transaction',
            'icon': 'fas fa-exchange-alt',
            'url': '/transactions/',
            'details': f'₱{transaction.amount} - {transaction.date.strftime("%b %d, %Y")}'
        })
    
    # Search payments
    payments = Payment.objects.filter(
        category__user=request.user
    ).filter(
        Q(category__name__icontains=query)
    )[:3]
    
    for payment in payments:
        results.append({
            'name': f'Payment for {payment.category.name}',
            'type': 'Payment',
            'icon': 'fas fa-money-bill-wave',
            'url': f'/category/{payment.category.id}/',
            'details': f'₱{payment.amount_paid} - {payment.payment_date.strftime("%b %d, %Y")}'
        })
    
    # Search for specific dates in due dates
    from datetime import datetime
    
    # Search for categories with due dates matching the query
    date_categories = Category.objects.filter(
        user=request.user,
        is_active=True,
        due_date__isnull=False
    )
    
    for category in date_categories:
        due_date_str = category.due_date.strftime('%B %d, %Y').lower()
        month_name = category.due_date.strftime('%B').lower()
        day_str = str(category.due_date.day)
        
        if (query in due_date_str or 
            query in month_name or 
            query == day_str or
            query in category.due_date.strftime('%b').lower()):
            results.append({
                'name': f'{category.name} - Due {category.due_date.strftime("%b %d")}',
                'type': 'Due Date',
                'icon': 'fas fa-calendar-alt',
                'url': f'/category/{category.id}/',
                'details': f'₱{category.amount} due on {category.due_date.strftime("%B %d, %Y")}'
            })
    
    # Search months for unpaid bills modal
    months = ['january', 'february', 'march', 'april', 'may', 'june', 
              'july', 'august', 'september', 'october', 'november', 'december']
    
    for i, month in enumerate(months, 1):
        if query in month:
            month_categories = Category.objects.filter(
                user=request.user,
                is_active=True,
                payment_status='unpaid',
                due_date__month=i,
                due_date__year=timezone.now().year
            ).count()
            
            results.append({
                'name': f'{month.capitalize()} Bills',
                'type': 'Month',
                'icon': 'fas fa-calendar',
                'url': f'javascript:viewUnpaidBills({i})',
                'details': f'{month_categories} unpaid bills in {month.capitalize()}'
            })
    
    # Search budget-related terms
    budget_terms = {
        'budget': {'url': '/', 'details': 'Monthly budget management'},
        'expense': {'url': '/transactions/', 'details': 'View all expenses'},
        'income': {'url': '/transactions/', 'details': 'View all income'},
        'monthly': {'url': '/', 'details': 'Monthly budget overview'},
        'yearly': {'url': '/', 'details': 'Yearly financial overview'},
        'bills': {'url': '/', 'details': 'Payment categories and bills'},
        'payment': {'url': '/', 'details': 'Payment management'},
        'due': {'url': '/', 'details': 'Due payments and reminders'},
        'overdue': {'url': '/', 'details': 'Overdue payments'},
        'paid': {'url': '/', 'details': 'Paid categories'},
        'unpaid': {'url': '/', 'details': 'Unpaid bills'},
    }
    
    for term, info in budget_terms.items():
        if query in term:
            results.append({
                'name': term.capitalize(),
                'type': 'Feature',
                'icon': 'fas fa-money-bill-wave',
                'url': info['url'],
                'details': info['details']
            })
    
    # Search category types
    category_types = ['rent', 'utilities', 'groceries', 'transportation', 'entertainment', 
                     'healthcare', 'education', 'insurance', 'savings', 'other']
    
    for cat_type in category_types:
        if query in cat_type:
            matching_categories = Category.objects.filter(
                user=request.user, 
                category_type=cat_type,
                is_active=True
            ).count()
            if matching_categories > 0:
                results.append({
                    'name': f'{cat_type.capitalize()} Categories',
                    'type': 'Category Type',
                    'icon': 'fas fa-tags',
                    'url': '/',
                    'details': f'{matching_categories} {cat_type} categories'
                })
    
    # Add static pages
    static_pages = [
        {'name': 'Home', 'url': '/', 'type': 'Page', 'icon': 'fas fa-home'},
        {'name': 'Profile', 'url': '/profile/', 'type': 'Page', 'icon': 'fas fa-user'},
        {'name': 'Transactions', 'url': '/transactions/', 'type': 'Page', 'icon': 'fas fa-exchange-alt'},
        {'name': 'Logo', 'url': '/logo/', 'type': 'Media', 'icon': 'fas fa-image'},
        {'name': 'Poster', 'url': '/poster/', 'type': 'Media', 'icon': 'fas fa-image'},
        {'name': 'Advertisement', 'url': '/advertisement/', 'type': 'Media', 'icon': 'fas fa-video'},
    ]
    
    for page in static_pages:
        if query in page['name'].lower():
            results.append({
                'name': page['name'],
                'type': page['type'],
                'icon': page['icon'],
                'url': page['url'],
                'details': f'{page["type"]} - PayFlow App'
            })
    
    return JsonResponse({'results': results[:20]})

@login_required
@redirect_staff_to_admin
def search_results(request):
    """Full search results page"""
    query = request.GET.get('q', '').strip()
    if not query:
        return redirect('home')
    
    # Search categories
    categories = Category.objects.filter(
        user=request.user, 
        is_active=True
    ).filter(
        Q(name__icontains=query) | 
        Q(category_type__icontains=query)
    )
    
    # Search transactions
    transactions = Transaction.objects.filter(
        user=request.user
    ).filter(
        Q(title__icontains=query) |
        Q(description__icontains=query)
    ).order_by('-date')
    
    # Search payments
    payments = Payment.objects.filter(
        category__user=request.user
    ).filter(
        Q(category__name__icontains=query)
    ).order_by('-payment_date')
    
    context = {
        'query': query,
        'categories': categories,
        'transactions': transactions,
        'payments': payments,
        'total_results': categories.count() + transactions.count() + payments.count()
    }
    
    return render(request, 'budget/search_results.html', context)

@login_required
def admin_search_suggestions(request):
    """API endpoint for admin user search suggestions"""
    if not request.user.is_staff:
        return JsonResponse({'results': []})
    
    query = request.GET.get('q', '').strip().lower()
    if not query:
        return JsonResponse({'results': []})
    
    results = []
    
    # Search users by username, first name, last name
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    )[:10]
    
    for user in users:
        full_name = f"{user.first_name} {user.last_name}".strip()
        role = "Admin" if user.is_staff else "User"
        
        results.append({
            'name': user.username,
            'type': role,
            'icon': 'fas fa-user-shield' if user.is_staff else 'fas fa-user',
            'username': user.username,
            'url': '/admin-dashboard/',
            'details': f'{full_name or "No name"} - Joined {user.date_joined.strftime("%b %Y")}'
        })
    
    # Search by role
    if 'admin' in query:
        admin_count = User.objects.filter(is_staff=True).count()
        results.append({
            'name': 'Admin Users',
            'type': 'Role Filter',
            'icon': 'fas fa-user-shield',
            'username': 'admin_filter',
            'url': '/admin-dashboard/',
            'details': f'{admin_count} admin users'
        })
    
    if 'user' in query:
        user_count = User.objects.filter(is_staff=False).count()
        results.append({
            'name': 'Regular Users',
            'type': 'Role Filter',
            'icon': 'fas fa-user',
            'username': 'user_filter',
            'url': '/admin-dashboard/',
            'details': f'{user_count} regular users'
        })
    
    return JsonResponse({'results': results[:15]})

def get_notifications_context(request):
    """Context processor to add notifications to all templates"""
    if request.user.is_authenticated:
        # Reset monthly categories if month has changed
        categories = Category.objects.filter(user=request.user, is_active=True, is_monthly=True)
        for category in categories:
            category.reset_for_new_month()
        
        # Get categories that are due soon (1-2 days) or overdue and are unpaid
        categories = Category.objects.filter(user=request.user, is_active=True, payment_status='unpaid')
        due_soon = []
        
        for category in categories:
            if category.is_due_soon or category.is_overdue:
                due_soon.append(category)
        
        return {'due_soon': due_soon}
    return {'due_soon': []}