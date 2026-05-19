from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notification
from django.shortcuts import get_object_or_404

@login_required
def notification_list(request):
    qs = (
        Notification.objects
        .filter(user=request.user, is_read=False)
        .only("id", "title", "message", "url", "is_read", "created_at")
        .order_by("-created_at")
    )

    unread_count = qs.count()
    items = qs[:10]

    return JsonResponse({
        "unread_count": unread_count,
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "url": n.url,
                "is_read": n.is_read,
            }
            for n in items
        ]
    })


@login_required
def mark_all_notifications_read(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True)

    return JsonResponse({"status": "ok"})

@login_required
def mark_notification_read(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    notification = get_object_or_404(
        Notification,
        pk=pk,
        user=request.user
    )

    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    return JsonResponse({"status": "ok"})