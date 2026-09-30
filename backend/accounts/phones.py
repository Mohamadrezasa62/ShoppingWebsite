import re

DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_iran_mobile(value):
    digits = str(value).strip().translate(DIGIT_TRANSLATION)
    if digits.startswith("0098"):
        digits = "+98" + digits[4:]
    elif digits.startswith("98"):
        digits = "+" + digits
    elif digits.startswith("09"):
        digits = "+98" + digits[1:]
    if not re.fullmatch(r"\+989\d{9}", digits):
        raise ValueError("Enter a valid Iranian mobile number")
    return digits


def normalize_code(value):
    return str(value).strip().translate(DIGIT_TRANSLATION)
