from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Show all users in the database'

    def handle(self, *args, **options):
        users = User.objects.all()
        
        if not users:
            self.stdout.write(self.style.WARNING('No users found in the database.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {users.count()} user(s) in the database:\n'))
        
        for user in users:
            self.stdout.write(f'Username: {user.username}')
            self.stdout.write(f'First Name: {user.first_name}')
            self.stdout.write(f'Last Name: {user.last_name}')
            self.stdout.write(f'Email: {user.email}')
            self.stdout.write(f'Password Hash: {user.password[:50]}...')  # Show first 50 chars of encrypted password
            self.stdout.write(f'Date Joined: {user.date_joined}')
            self.stdout.write(f'Is Active: {user.is_active}')
            self.stdout.write('-' * 50)
