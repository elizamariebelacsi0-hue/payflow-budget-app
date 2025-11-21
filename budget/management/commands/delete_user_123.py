from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Delete the fake user "123" that should not exist'

    def handle(self, *args, **options):
        username = '123'
        
        try:
            user = User.objects.get(username=username)
            user.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted fake user "{username}"!')
            )
            self.stdout.write(
                self.style.SUCCESS('Now users cannot login with fake accounts.')
            )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'User "{username}" does not exist.')
            )
