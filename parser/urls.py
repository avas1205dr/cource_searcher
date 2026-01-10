from django.urls import path

from parser.views import *

app_name = "parser"

urlpatterns = [
    path("", main_view, name="main")
]
