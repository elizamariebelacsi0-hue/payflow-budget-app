from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Make user "eli" a staff user so they can access admin'

    def handle(self, *args, **options):
        username = 'eli'
        
        try:
            user = User.objects.get(username=username)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully made user "{username}" a staff user!'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'You can now login to admin at http://127.0.0.1:8000/admin/ with username: {username}'
                )
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User "{username}" does not exist!')
            )
