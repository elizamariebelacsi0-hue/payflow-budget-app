from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from budget.models import Category
from datetime import timedelta

class Command(BaseCommand):
    help = 'Send payment reminders for categories due soon'

    def handle(self, *args, **options):
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)
        
        # Get categories due in the next 2 days
        due_soon_categories = Category.objects.filter(
            is_active=True,
            due_date__in=[today, tomorrow, day_after_tomorrow]
        ).select_related('user')
        
        if due_soon_categories:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Found {due_soon_categories.count()} categories due soon'
                )
            )
            
            for category in due_soon_categories:
                days_until_due = (category.due_date - today).days
                status = "OVERDUE" if days_until_due < 0 else f"Due in {days_until_due} day(s)"
                
                self.stdout.write(
                    f'User: {category.user.username} | '
                    f'Category: {category.name} | '
                    f'Amount: ₱{category.amount} | '
                    f'Due: {category.due_date} | '
                    f'Status: {status}'
                )
        else:
            self.stdout.write(
                self.style.SUCCESS('No categories due soon')
            )
