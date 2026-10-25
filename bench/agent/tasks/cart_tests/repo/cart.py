"""Shopping cart totals."""

TAX_RATE = 0.08


def cart_total(items, discount_code=None):
    """Total for items [(unit_price, quantity)], after an optional discount and then tax, rounded to cents.

    SAVE10 takes 10% off the subtotal. FLAT5 takes 5 off when the subtotal is at least 20.
    Unknown codes raise ValueError, and so does a quantity that is not a positive integer.
    """
    subtotal = 0.0
    for price, qty in items:
        if not isinstance(qty, int) or qty <= 0:
            raise ValueError("quantity must be a positive integer")
        subtotal += price * qty
    if discount_code is None:
        discounted = subtotal
    elif discount_code == "SAVE10":
        discounted = subtotal * 0.9
    elif discount_code == "FLAT5":
        discounted = subtotal - 5 if subtotal >= 20 else subtotal
    else:
        raise ValueError("unknown discount code")
    return round(discounted * (1 + TAX_RATE), 2)
