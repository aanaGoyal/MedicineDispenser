from django.core.exceptions import ValidationError
import re

def strong_password(value):
    if not re.findall('[A-Z]', value):
        raise ValidationError("The password must contain at least 1 uppercase letter.")
    if not re.findall('[a-z]', value):
        raise ValidationError("The password must contain at least 1 lowercase letter.")
    if not re.findall('[0-9]', value):
        raise ValidationError("The password must contain at least 1 digit.")
    if not re.findall('[^A-Za-z0-9]', value):
        raise ValidationError("The password must contain at least 1 special character.")
