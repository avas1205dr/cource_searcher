from django.urls import path

from parser.views import *

app_name = "parser"

urlpatterns = [
    path('', MainPageView.as_view(), name='main'),
    path('course/<int:pk>/', CourseDetailView.as_view(), name='course_detail'),
]
