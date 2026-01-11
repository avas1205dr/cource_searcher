from django.views.generic import ListView, DetailView, TemplateView
from django.db.models import Avg, Count, Q, Max
from parser.models import Course, Category, Review


class MainPageView(ListView):
    model = Course
    template_name = "parser/main.html"
    context_object_name = "courses"
    paginate_by = 12

    def get_queryset(self):
        queryset = (
            Course.objects.filter(is_active=True, is_public=True)
            .with_rating()
            .select_related()
            .prefetch_related("course_lists", "authors", "instructors")
        )

        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(summary__icontains=search_query)
            )

        platform = self.request.GET.get("platform", "")
        if platform:
            queryset = queryset.filter(platform=platform)

        language = self.request.GET.get("language", "")
        if language:
            queryset = queryset.filter(language=language)

        price_filter = self.request.GET.get("price", "")
        if price_filter == "free":
            queryset = queryset.filter(is_paid=False)
        elif price_filter == "paid":
            queryset = queryset.filter(is_paid=True)

        sort_by = self.request.GET.get("sort", "")
        if sort_by == "alphabet":
            queryset = queryset.order_by("title")
        elif sort_by == "alphabet_desc":
            queryset = queryset.order_by("-title")

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["total_courses"] = Course.objects.filter(
            is_active=True, is_public=True
        ).count()

        context["stepik_courses"] = Course.objects.filter(
            is_active=True, is_public=True, platform="stepik"
        ).count()

        context["other_courses"] = (
            context["total_courses"] - context["stepik_courses"]
        )

        context["search_query"] = self.request.GET.get("search", "")
        context["selected_platform"] = self.request.GET.get("platform", "")
        context["selected_language"] = self.request.GET.get("language", "")
        context["selected_sort"] = self.request.GET.get("sort", "")
        context["selected_price"] = self.request.GET.get("price", "")

        return context


class CourseDetailView(DetailView):
    model = Course
    template_name = "parser/course.html"
    context_object_name = "course"

    def get_queryset(self):
        return (
            Course.objects.filter(is_active=True, is_public=True)
            .with_rating()
            .prefetch_related(
                "course_lists__category",
                "authors",
                "instructors",
                "reviews__user",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object

        reviews = course.reviews.select_related("user").order_by(
            "-create_date"
        )[:10]
        context["reviews"] = reviews

        reviews_stats = course.reviews.aggregate(
            total=Count("id"),
            score_5=Count("id", filter=Q(score=5)),
            score_4=Count("id", filter=Q(score=4)),
            score_3=Count("id", filter=Q(score=3)),
            score_2=Count("id", filter=Q(score=2)),
            score_1=Count("id", filter=Q(score=1)),
        )
        context["reviews_stats"] = reviews_stats

        similar_courses = (
            Course.objects.filter(
                is_active=True,
                is_public=True,
                course_lists__in=course.course_lists.all(),
            )
            .exclude(id=course.id)
            .with_rating()
            .distinct()[:3]
        )
        context["similar_courses"] = similar_courses

        return context


class StatsView(TemplateView):
    template_name = "parser/stats.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        courses = Course.objects.filter(is_active=True, is_public=True)

        context["total_courses"] = courses.count()

        avg_rating = courses.with_rating().aggregate(avg=Avg("rating_avg"))[
            "avg"
        ]
        context["avg_rating"] = round(avg_rating, 1) if avg_rating else 0

        max_students = courses.aggregate(max=Max("learners_count"))["max"] or 0
        context["max_students"] = max_students

        context["total_reviews"] = Review.objects.count()

        lang_stats = (
            courses.values("language")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        total = context["total_courses"]
        context["lang_stats"] = [
            {
                "name": dict(Course.LANGUAGE_CHOICES).get(
                    item["language"], "Не указан"
                ),
                "count": item["count"],
                "percent": (
                    round(item["count"] / total * 100, 1) if total > 0 else 0
                ),
            }
            for item in lang_stats
        ]

        price_stats = courses.aggregate(
            free=Count("id", filter=Q(is_paid=False)),
            paid=Count("id", filter=Q(is_paid=True)),
        )
        context["price_stats"] = {
            "free": {
                "count": price_stats["free"],
                "percent": (
                    round(price_stats["free"] / total * 100, 1)
                    if total > 0
                    else 0
                ),
            },
            "paid": {
                "count": price_stats["paid"],
                "percent": (
                    round(price_stats["paid"] / total * 100, 1)
                    if total > 0
                    else 0
                ),
            },
        }

        platform_stats = (
            courses.values("platform")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        context["platform_stats"] = [
            {
                "name": dict(Course.PLATFORM_CHOICES).get(
                    item["platform"], item["platform"]
                ),
                "count": item["count"],
                "percent": (
                    round(item["count"] / total * 100, 1) if total > 0 else 0
                ),
            }
            for item in platform_stats
        ]

        context["top_popular"] = courses.order_by("-learners_count")[:10]

        context["top_rated"] = (
            courses.with_rating()
            .filter(reviews_count_calc__gte=5)
            .exclude(rating_avg__isnull=True)
            .order_by("-rating_avg", "-reviews_count_calc")[:10]
        )

        context["courses_with_reviews"] = courses.filter(
            reviews_count__gt=0
        ).count()

        avg_duration = courses.filter(
            time_to_complete__isnull=False
        ).aggregate(avg=Avg("time_to_complete"))["avg"]
        context["avg_duration"] = (
            round(avg_duration / 3600, 1) if avg_duration else 0
        )

        category_stats = (
            Category.objects.annotate(
                course_count=Count(
                    "course_lists__courses",
                    filter=Q(
                        course_lists__courses__is_active=True,
                        course_lists__courses__is_public=True,
                    ),
                    distinct=True,
                )
            )
            .filter(course_count__gt=0)
            .order_by("-course_count")[:5]
        )
        context["category_stats"] = category_stats

        return context
