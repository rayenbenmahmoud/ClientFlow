from django.core.validators import RegexValidator

PHONE_VALIDATOR = RegexValidator(
    r"^[0-9+()\-.\s]{5,40}$",
    "Enter a valid phone number (digits, spaces and + ( ) - . only; 5-40 characters).",
)
HEX_COLOR_VALIDATOR = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Enter a color like #3b82f6.")
