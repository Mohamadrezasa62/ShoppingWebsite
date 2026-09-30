from catalog.models import Offer, Product
from sellers.models import Seller


def address_data(address):
    return {
        "id": address.pk, "full_name": address.full_name, "phone": address.phone,
        "province": address.province, "city": address.city,
        "street": address.street, "postal_code": address.postal_code,
    }


def offer_is_visible(offer):
    product = offer.variant.product
    return (
        offer.status == Offer.Status.ACTIVE
        and offer.seller.status == Seller.Status.APPROVED
        and offer.variant.is_active
        and product.status == Product.Status.PUBLISHED
        and product.category.is_active
        and (product.brand is None or product.brand.is_active)
    )
