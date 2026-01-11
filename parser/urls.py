from django.urls import path

from parser.views import *

app_name = "parser"

urlpatterns = [
    path('', MainPageView.as_view(), name='main'),
]
