from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'List all users in the database'

    def handle(self, *args, **options):
        users = User.objects.all()
        
        if users.exists():
            self.stdout.write(self.style.SUCCESS(f'Found {users.count()} user(s):'))
            for user in users:
                self.stdout.write(
                    f'  - Username: "{user.username}" | '
                    f'Email: "{user.email}" | '
                    f'Staff: {user.is_staff} | '
                    f'Superuser: {user.is_superuser} | '
                    f'Active: {user.is_active}'
                )
        else:
            self.stdout.write(self.style.WARNING('No users found in database!'))
