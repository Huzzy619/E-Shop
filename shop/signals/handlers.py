
from django.dispatch import receiver
from shop.models import TrackOrder
from shop.signals import order_created

@receiver(order_created)
def start_tracking(sender, **kwargs):

    # if kwargs['created']:
    tracks = [
        TrackOrder(
        order = order
    )
    for order in kwargs['instances']]
    TrackOrder.objects.bulk_create(tracks)
