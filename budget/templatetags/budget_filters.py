from django import template
from django.template.defaultfilters import floatformat

register = template.Library()

@register.filter
def money_format(value):
    """
    Format money amounts with thousand separators (commas)
    Example: 1000.50 -> 1,000.50
    """
    if value is None:
        return "0.00"
    
    # Convert to float and format with 2 decimal places
    try:
        float_value = float(value)
        # Format with commas for thousands
        formatted = "{:,.2f}".format(float_value)
        return formatted
    except (ValueError, TypeError):
        return "0.00"

@register.filter
def peso_format(value):
    """
    Format money amounts with peso symbol and thousand separators
    Example: 1000.50 -> ₱1,000.50
    """
    formatted = money_format(value)
    return f"₱{formatted}"

@register.filter
def accurate_amount(value):
    """
    Format amounts accurately without rounding issues
    Example: 400.00 -> 400, 400.50 -> 400.50
    """
    if value is None:
        return "0"
    
    try:
        # Convert to Decimal for precise handling
        from decimal import Decimal
        decimal_value = Decimal(str(value))
        
        # If it's a whole number, display without decimals
        if decimal_value == decimal_value.quantize(Decimal('1')):
            return str(int(decimal_value))
        else:
            # Display with appropriate decimal places
            return str(decimal_value.normalize())
    except (ValueError, TypeError):
        return "0"