"""Each mutant is (description, old text, new text) applied to cart.py. Tests that pass on cart.py and fail on a
mutant have caught it."""
MUTANTS = [
    ("tax ignored", "discounted * (1 + TAX_RATE)", "discounted"),
    ("tax before discount", "return round(discounted * (1 + TAX_RATE), 2)", "return round(discounted * (1 + TAX_RATE), 2) if discount_code is None else round(subtotal * (1 + TAX_RATE) - (subtotal - discounted), 2)"),
    ("SAVE10 is 20%", "subtotal * 0.9", "subtotal * 0.8"),
    ("FLAT5 threshold strict", "subtotal >= 20", "subtotal > 20"),
    ("FLAT5 always applies", "subtotal - 5 if subtotal >= 20 else subtotal", "subtotal - 5"),
    ("zero quantity allowed", "qty <= 0", "qty < 0"),
    ("float quantity allowed", "not isinstance(qty, int) or ", ""),
    ("unknown code ignored", "        raise ValueError(\"unknown discount code\")", "        discounted = subtotal"),
    ("quantity ignored", "subtotal += price * qty", "subtotal += price"),
    ("no rounding", "return round(discounted * (1 + TAX_RATE), 2)", "return discounted * (1 + TAX_RATE)"),
]
