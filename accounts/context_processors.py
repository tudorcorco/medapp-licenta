def language_context(request):
    return {
        'lang': request.session.get('lang', 'ro'),
    }