from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from budget.models import UserProfile

class Command(BaseCommand):
    help = 'Create a user with username and password both "123"'

    def handle(self, *args, **options):
        username = '123'
        password = '123'
        email = '123@example.com'
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists!')
            )
            return
        
        # Create the user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name='User',
            last_name='123'
        )
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created user "{username}" with password "{password}"'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'You can now login at http://127.0.0.1:8000/admin/ with username: {username} and password: {password}'
            )
        )
