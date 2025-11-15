from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserProfile
from User.models import CustomUser

User = get_user_model()

@receiver(post_save, sender=CustomUser) # Ensure the sender is CustomUser
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        # Pass the roll_no from the new user to the UserProfile
        UserProfile.objects.get_or_create(user=instance, roll_no=instance.roll_no)
