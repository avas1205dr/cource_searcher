from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
import threading

from .models import Category, CourseList, StepikUser, Course, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'external_id', 'course_lists_count', 'created_at']
    search_fields = ['title', 'description', 'external_id']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    def course_lists_count(self, obj):
        return obj.course_lists.count()
    course_lists_count.short_description = 'Списков курсов'

@admin.register(CourseList)
class CourseListAdmin(admin.ModelAdmin):
    list_display = ['title', 'external_id', 'category', 'courses_count', 'created_at']
    search_fields = ['title', 'description', 'external_id']
    list_filter = ['category', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['category']
    
    def courses_count(self, obj):
        return obj.courses.count()
    courses_count.short_description = 'Курсов'


@admin.register(StepikUser)
class StepikUserAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'external_id', 'authored_count', 'instructed_count', 'created_at']
    search_fields = ['full_name', 'bio', 'external_id']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at', 'avatar', 'details']
    
    def authored_count(self, obj):
        return obj.authored_courses.count()
    authored_count.short_description = 'Курсов (автор)'
    
    def instructed_count(self, obj):
        return obj.instructed_courses.count()
    instructed_count.short_description = 'Курсов (преподаватель)'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'external_id', 'learners_count', 'is_paid', 'is_active', 'language', 'created_at', "rating_display", "reviews_count_display"
    ]
    search_fields = ['title', 'description', 'summary', 'external_id', 'slug']
    list_filter = ['is_paid', 'is_active', 'is_public', 'is_featured', 'language', 'created_at', 'course_lists']
    readonly_fields = ['created_at', 'updated_at', 'cover', 'raw_data', "rating_display", "reviews_count_display"]
    filter_horizontal = ['course_lists', 'authors', 'instructors']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.with_rating()

    def rating_display(self, obj):
        return obj.rating_avg

    rating_display.short_description = "Рейтинг"
    rating_display.admin_order_field = "rating_avg"

    def reviews_count_display(self, obj):
        return obj.reviews_count_calc

    reviews_count_display.short_description = "Оценок"
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('external_id', 'title', 'slug', 'description', 'summary', 'cover')
        }),
        ('Характеристики', {
            'fields': ('is_paid', 'price', 'learners_count', 'time_to_complete', 'language')
        }),
        ('Статус', {
            'fields': ('is_active', 'is_public', 'is_featured')
        }),
        ('Рейтинг', {
            'fields': ('rating_display', 'reviews_count_display')
        }),
        ('Связи', {
            'fields': ('course_lists', 'authors', 'instructors')
        }),
        ('Дополнительно', {
            'fields': ('raw_data',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['external_id', 'course_title', 'user_name', 'score', 'create_date']
    search_fields = ['text', 'external_id', 'course__title', 'user__full_name']
    list_filter = ['score', 'create_date']
    readonly_fields = ['created_at', 'updated_at', 'raw_data']
    autocomplete_fields = ['course', 'user']
    
    def course_title(self, obj):
        return obj.course.title if obj.course else '-'
    course_title.short_description = 'Курс'
    
    def user_name(self, obj):
        return obj.user.full_name if obj.user else '-'
    user_name.short_description = 'Пользователь'


class ParserAdminSite(admin.AdminSite):
    site_header = 'Сбор информации со Stepik'
    site_title = 'Парсер Stepik'
    index_title = 'Административная панель Курсовика'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('run-parser/', self.admin_view(self.run_parser_view), name='run_parser'),
        ]
        return custom_urls + urls
    
    def run_parser_view(self, request):
        if request.method == 'POST':
            def run_parser():
                try:
                    call_command('run_stepik_parser')
                except Exception as e:
                    print(f"Ошибка парсера: {e}")
            
            thread = threading.Thread(target=run_parser)
            thread.start()
            
            messages.success(request, 'Парсер запущен в фоновом режиме! Следите за прогрессом в консоли.')
            return redirect('admin:index')
        
        return render(request, 'admin/run_parser.html')
    
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_parser_button'] = True
        return super().index(request, extra_context)


admin_site = ParserAdminSite(name='admin')

admin_site.register(Category, CategoryAdmin)
admin_site.register(CourseList, CourseListAdmin)
admin_site.register(StepikUser, StepikUserAdmin)
admin_site.register(Course, CourseAdmin)
admin_site.register(Review, ReviewAdmin)