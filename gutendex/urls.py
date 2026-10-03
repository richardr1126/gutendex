from django.db import connection
from django.http import JsonResponse
from django.urls import include, re_path
from django.views.generic import TemplateView

from rest_framework import routers

from books import views


def healthz(request):
    # Readiness, so it asks the database: an API that cannot reach Postgres
    # should be taken out of the Service rather than answer every request 500.
    connection.ensure_connection()
    return JsonResponse({'status': 'ok'})


router = routers.DefaultRouter()
router.register(r'books', views.BookViewSet)

urlpatterns = [
    re_path(r'^$', TemplateView.as_view(template_name='home.html')),
    re_path(r'^healthz$', healthz),
    re_path(r'^', include(router.urls)),
]
