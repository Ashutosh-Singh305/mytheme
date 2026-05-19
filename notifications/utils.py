from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_notification(user_id, payload: dict):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            "type": "notify",
            "data": payload
        }
    )
# Socket programming is for the real time application where the data is transfered in real time without refreshing the page.