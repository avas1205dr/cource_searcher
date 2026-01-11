from django.urls import path, include

from parser.admin import admin_site

urlpatterns = [
    path("admin/", admin_site.urls),
    path("", include("parser.urls", namespace="parser")),
]
