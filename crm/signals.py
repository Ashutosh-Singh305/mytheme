# crm/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from crm.models import Lead
from notifications.utils import send_notification
from notifications.models import Notification

@receiver(post_save, sender=Lead)
def lead_created(sender, instance, created, **kwargs):
    if not created:
        return

    user = instance.assigned_to
    if not user:
        return

    Notification.objects.create(
        user=user,
        title=f"New Lead Assigned : {instance.assigned_to}",
        message=f"Lead {instance.name} assigned to you.",
        url=f"/crm/Lead/{instance.pk}/"
    )

    
    
    send_notification(
            user.id,
            {
                "title": "New Lead Assigned",
                "message":f"Lead {instance.name} assigned to you.",
                "url": f"/crm/Lead/{instance.pk}/",
            }
        )
    

