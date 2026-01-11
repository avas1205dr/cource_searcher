from django.db import models
from django.db.models.functions import Round


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Изменено")

    class Meta:
        abstract = True


class ExternalEntityModel(TimestampedModel):
    external_id = models.IntegerField(unique=True, db_index=True, verbose_name="ID на Stepik")

    class Meta:
        abstract = True


class CourseQuerySet(models.QuerySet):
    def with_rating(self):
        return self.annotate(
            rating_avg=Round(
                models.Avg("reviews__score"),
                0,
                output_field=models.DecimalField(max_digits=3,
                decimal_places=2),
            ),
            reviews_count_calc=models.Count("reviews"),
        )

class CourseManager(models.Manager):
    def get_queryset(self):
        return CourseQuerySet(self.model, using=self._db)
    
    def with_rating(self):
        return self.get_queryset().with_rating()

class Category(ExternalEntityModel):
    title = models.CharField(max_length=500, verbose_name="Категория")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["title"]

    def __str__(self):
        return self.title


class CourseList(ExternalEntityModel):
    title = models.CharField(max_length=500, verbose_name="Подкатегория")
    description = models.TextField(blank=True, verbose_name="Описание")
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="course_lists",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Подкатегория"
        verbose_name_plural = "Подкатегории"

    def __str__(self):
        return self.title


class StepikUser(ExternalEntityModel):
    full_name = models.CharField(max_length=500, blank=True, verbose_name="ФИО")
    avatar = models.URLField(blank=True, max_length=1000, verbose_name="Фото профиля")
    bio = models.TextField(blank=True, verbose_name="Описание профиля")
    details = models.JSONField(default=dict, blank=True, verbose_name="Дополнительная информация")

    class Meta:
        verbose_name = "Пользователь на Stepik"
        verbose_name_plural = "Пользователи на Stepik"

    def __str__(self):
        return self.full_name or f"Пользователь {self.external_id}"


class Course(ExternalEntityModel):
    title = models.CharField(max_length=500, verbose_name="Курс")
    slug = models.SlugField(max_length=500, blank=True, verbose_name="Слаг")
    description = models.TextField(blank=True, verbose_name="Описание")
    summary = models.TextField(blank=True, verbose_name="О курсе")
    cover = models.URLField(blank=True, max_length=1000, verbose_name="Обложка")
    is_paid = models.BooleanField(default=False, verbose_name="Платный")
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Цена",
    )
    learners_count = models.IntegerField(default=0, verbose_name="Количество записавшихся")
    time_to_complete = models.IntegerField(null=True, blank=True, verbose_name="Время на выполнение (ак.ч.)")
    language = models.CharField(max_length=10, blank=True, verbose_name="Язык")
    is_active = models.BooleanField(default=True, verbose_name="Активный")
    is_public = models.BooleanField(default=True, verbose_name="Опубликован")
    is_featured = models.BooleanField(default=False, verbose_name="Запись ещё не началась")
    reviews_count = models.IntegerField(default=0, verbose_name="Количество оценок")
    course_lists = models.ManyToManyField(
        CourseList, related_name="courses", blank=True, verbose_name="Подкатегории"
    )
    authors = models.ManyToManyField(
        StepikUser, related_name="authored_courses", blank=True, verbose_name="Авторы"
    )
    instructors = models.ManyToManyField(
        StepikUser, related_name="instructed_courses", blank=True, verbose_name="Преподаватели"
    )
    raw_data = models.JSONField(default=dict, blank=True, verbose_name="Данные с запроса")

    objects = CourseManager()
    
    class Meta:
        ordering = ["-learners_count"]
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"

    def __str__(self):
        return self.title


class Review(ExternalEntityModel):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="reviews", verbose_name="Отзыв"
    )
    user = models.ForeignKey(
        StepikUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reviews",
        verbose_name="Пользователь",
    )
    score = models.IntegerField(verbose_name="Оценка")
    text = models.TextField(blank=True, verbose_name="Комментарий к отзыву")
    create_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата публикации")
    update_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата изменения")
    raw_data = models.JSONField(default=dict, blank=True, verbose_name="Данные с запроса")

    class Meta:
        ordering = ["-create_date"]
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return f"Отзыв {self.external_id} на курс '{self.course.title}'"
