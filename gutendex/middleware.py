import hmac

from django.conf import settings
from django.http import JsonResponse


class ForceHttpsMiddleware:
    """Treats every request as HTTPS when `FORCE_HTTPS` is set.

    TLS ends at Cloudflare, so Django never sees HTTPS itself. Rewriting the
    WSGI scheme, rather than trusting a forwarded header, makes the absolute
    `next` and `previous` links say https:// whatever the proxies in between
    did to the headers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.FORCE_HTTPS:
            request.META['wsgi.url_scheme'] = 'https'
        return self.get_response(request)


class ApiKeyMiddleware:
    """Requires one of `API_KEYS` on every request but the health check."""

    exempt_paths = {'/healthz'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.API_KEYS and request.path not in self.exempt_paths:
            supplied = request.headers.get('X-API-Key', '')
            authorization = request.headers.get('Authorization', '')
            if not supplied and authorization.startswith('Bearer '):
                supplied = authorization[len('Bearer '):]
            if not self.is_valid(supplied.strip()):
                return JsonResponse({'detail': 'A valid API key is required.'}, status=401)
        return self.get_response(request)

    @staticmethod
    def is_valid(supplied):
        if not supplied:
            return False
        # Constant time, and every key compared, so the response time says
        # nothing about how close a guess was or which key it was near.
        matches = [hmac.compare_digest(supplied.encode(), key.encode()) for key in settings.API_KEYS]
        return any(matches)
