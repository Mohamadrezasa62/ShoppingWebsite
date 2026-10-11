from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Category, Offer, Product, Variant
from catalog.inventory import activate
from commerce.models import Address, ShippingRule
from sellers.models import Seller, SellerMembership


class Command(BaseCommand):
    help = "Create a repeatable, non-production two-seller catalog; no passwords or paid orders."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data is allowed only with DJANGO_DEBUG=1")
        buyer, _ = get_user_model().objects.get_or_create(phone="+989000000001")
        category, _ = Category.objects.get_or_create(slug="demo-phones", defaults={"name": "گوشی نمونه"})
        product, _ = Product.objects.get_or_create(slug="demo-phone", defaults={
            "title": "گوشی نمایشی", "category": category, "status": Product.Status.PUBLISHED,
            "description": "محصول نمونه برای محیط توسعه؛ قابل خرید واقعی نیست.",
        })
        variant, _ = Variant.objects.get_or_create(sku="DEMO-PHONE-128", defaults={"product": product, "attributes": {"storage": "128GB"}})
        for index in (1, 2):
            owner, _ = get_user_model().objects.get_or_create(phone=f"+98900000000{index + 1}")
            # Membership is the stable identity; repeated runs never create a second store.
            membership = owner.seller_memberships.filter(role=SellerMembership.Role.OWNER).first()
            if membership:
                seller = membership.seller
            else:
                seller = Seller.objects.create(name=f"فروشگاه نمونه {index}", status=Seller.Status.APPROVED)
                SellerMembership.objects.create(user=owner, seller=seller, role=SellerMembership.Role.OWNER)
            offer, _ = Offer.objects.get_or_create(seller=seller, variant=variant, defaults={
                "price_toman": 10_000_000 + index * 100_000, "available_quantity": 10,
                "status": Offer.Status.ACTIVE,
            })
            activate(offer.pk)
        Address.objects.get_or_create(user=buyer, postal_code="1234567890", defaults={
            "full_name": "خریدار نمونه", "phone": buyer.phone,
            "province": "تهران", "city": "تهران", "street": "نشانی نمایشی توسعه",
        })
        ShippingRule.objects.get_or_create(province="تهران", fulfillment="seller", defaults={
            "fee_toman": 50000, "min_days": 2, "max_days": 4,
        })
        self.stdout.write(self.style.SUCCESS("Demo catalog ready: demo-phone, two sellers. No credentials created."))
