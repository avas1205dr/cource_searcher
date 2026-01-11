from django.views.generic import ListView, DetailView
from django.db.models import Count, Q
from .models import Course


class MainPageView(ListView):
    model = Course
    template_name = 'parser/main.html'
    context_object_name = 'courses'
    paginate_by = 12

    def get_queryset(self):
        queryset = Course.objects.filter(
            is_active=True,
            is_public=True
        ).with_rating().select_related().prefetch_related(
            'course_lists',
            'authors',
            'instructors'
        )

        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(summary__icontains=search_query)
            )

        platform = self.request.GET.get('platform', '')
        if platform:
            queryset = queryset.filter(platform=platform)

        language = self.request.GET.get('language', '')
        if language:
            queryset = queryset.filter(language=language)

        price_filter = self.request.GET.get('price', '')
        if price_filter == 'free':
            queryset = queryset.filter(is_paid=False)
        elif price_filter == 'paid':
            queryset = queryset.filter(is_paid=True)

        sort_by = self.request.GET.get('sort', '')
        if sort_by == 'alphabet':
            queryset = queryset.order_by('title')
        elif sort_by == 'alphabet_desc':
            queryset = queryset.order_by('-title')

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['total_courses'] = Course.objects.filter(
            is_active=True,
            is_public=True
        ).count()
        
        context['stepik_courses'] = Course.objects.filter(
            is_active=True,
            is_public=True,
            platform='stepik'
        ).count()
        
        context['other_courses'] = context['total_courses'] - context['stepik_courses']

        context['search_query'] = self.request.GET.get('search', '')
        context['selected_platform'] = self.request.GET.get('platform', '')
        context['selected_language'] = self.request.GET.get('language', '')
        context['selected_sort'] = self.request.GET.get('sort', '')
        context['selected_price'] = self.request.GET.get('price', '')

        return context

class CourseDetailView(DetailView):
    model = Course
    template_name = 'parser/course.html'
    context_object_name = 'course'

    def get_queryset(self):
        return Course.objects.filter(
            is_active=True,
            is_public=True
        ).with_rating().prefetch_related(
            'course_lists__category',
            'authors',
            'instructors',
            'reviews__user'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object

        reviews = course.reviews.select_related('user').order_by('-create_date')[:10]
        context['reviews'] = reviews

        reviews_stats = course.reviews.aggregate(
            total=Count('id'),
            score_5=Count('id', filter=Q(score=5)),
            score_4=Count('id', filter=Q(score=4)),
            score_3=Count('id', filter=Q(score=3)),
            score_2=Count('id', filter=Q(score=2)),
            score_1=Count('id', filter=Q(score=1)),
        )
        context['reviews_stats'] = reviews_stats

        similar_courses = Course.objects.filter(
            is_active=True,
            is_public=True,
            course_lists__in=course.course_lists.all()
        ).exclude(id=course.id).with_rating().distinct()[:3]
        context['similar_courses'] = similar_courses

        return context
