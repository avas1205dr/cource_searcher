from django import template

register = template.Library()

@register.filter
def humanize_number(value):
    try:
        value = float(value)
        if value >= 1000000:
            return f"{value / 1000000:.1f}M"
        elif value >= 1000:
            return f"{value / 1000:.1f}K"
        else:
            return f"{int(value)}"
    except (ValueError, TypeError):
        return value