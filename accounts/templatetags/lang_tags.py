from django import template
from accounts.translations import T

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, text):
    lang = context.get('lang', 'ro')
    if lang == 'en':
        return T.get(text, text)
    return text