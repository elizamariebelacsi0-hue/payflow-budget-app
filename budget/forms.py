from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, Category, Payment, Transaction, MonthlyBudget

class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    role = forms.ChoiceField(
        choices=(
            ('user', 'User'),
            ('admin', 'Admin'),
        ),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'password1', 'password2')

class UserProfileForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    
    class Meta:
        model = UserProfile
        fields = ['profile_picture', 'birth_date', 'address', 'phone_number']
        widgets = {
            'birth_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter your address'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your phone number'
            }),
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),

        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            # Pre-populate User fields
            self.fields['username'].initial = self.instance.user.username
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            # Update User fields
            user = profile.user
            user.username = self.cleaned_data['username']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.save()
        return profile

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'amount', 'due_date', 'category_type', 'is_monthly']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category_type': forms.Select(attrs={'class': 'form-control'}),
            'is_monthly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'is_monthly': 'Automatically remind every month',
        }

class CategoryEditForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'amount', 'due_date', 'category_type', 'is_monthly']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category_type': forms.Select(attrs={'class': 'form-control'}),
            'is_monthly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'is_monthly': 'Automatically remind every month',
        }

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_type', 'amount_paid', 'payment_date', 'payment_method', 'transaction_id', 'gcash_account_used', 'proof_image', 'notes']
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount_paid': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., GCash Ref No.'}),
            'gcash_account_used': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'GCash account number used'}),

            'proof_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional payment notes'}),
        }

    def __init__(self, *args, **kwargs):
        self.category = kwargs.pop('category', None)
        super().__init__(*args, **kwargs)
        if self.category:
            self.fields['amount_paid'].widget.attrs['max'] = str(self.category.amount)
            self.fields['amount_paid'].initial = self.category.amount

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        payment_type = cleaned_data.get('payment_type')
        amount_paid = cleaned_data.get('amount_paid')
        transaction_id = cleaned_data.get('transaction_id')
        gcash_account_used = cleaned_data.get('gcash_account_used')
        
        if payment_method == 'gcash':
            if not transaction_id:
                self.add_error('transaction_id', 'Transaction ID is required for GCash payments.')
            if not gcash_account_used:
                self.add_error('gcash_account_used', 'GCash account number used is required for GCash payments.')
        
        if self.category and amount_paid:
            if payment_type == 'full' and amount_paid != self.category.amount:
                self.add_error('amount_paid', f'Full payment must be exactly ₱{self.category.amount}')
            elif payment_type == 'partial' and amount_paid >= self.category.amount:
                self.add_error('amount_paid', f'Partial payment must be less than ₱{self.category.amount}')
            elif amount_paid > self.category.amount:
                self.add_error('amount_paid', f'Payment cannot exceed ₱{self.category.amount}')
        
        return cleaned_data

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['title', 'amount', 'transaction_type', 'category', 'date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

class MonthlyBudgetForm(forms.ModelForm):
    class Meta:
        model = MonthlyBudget
        fields = ['total_budget']
        widgets = {
            'total_budget': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

class AdditionalBudgetForm(forms.Form):
    amount_added = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'min': '0.01',
            'class': 'form-control',
            'placeholder': 'Enter amount to add'
        }),
        label='Additional Budget Amount'
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes (e.g., "Extra income from side job")'
        }),
        label='Notes (Optional)'
    ) 