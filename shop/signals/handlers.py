
from django.dispatch import receiver
from shop.models import TrackOrder
from shop.signals import order_created

@receiver(order_created)
def start_tracking(sender, **kwargs):

    # if kwargs['created']:
    TrackOrder.objects.create(order = kwargs['instance'])
