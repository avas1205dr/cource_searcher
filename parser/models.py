from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ExternalEntityModel(TimestampedModel):
    external_id = models.IntegerField(unique=True, db_index=True)

    class Meta:
        abstract = True


class Category(ExternalEntityModel):
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["title"]

    def __str__(self):
        return self.title


class CourseList(ExternalEntityModel):
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="course_lists",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.title


class StepikUser(ExternalEntityModel):
    full_name = models.CharField(max_length=500, blank=True)
    avatar = models.URLField(blank=True, max_length=1000)
    bio = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.full_name or f"Пользователь {self.external_id}"


class Course(ExternalEntityModel):
    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    cover = models.URLField(blank=True, max_length=1000)
    is_paid = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=10, blank=True)
    learners_count = models.IntegerField(default=0)
    time_to_complete = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=10, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    reviews_count = models.IntegerField(default=0)
    course_lists = models.ManyToManyField(
        CourseList, related_name="courses", blank=True
    )
    authors = models.ManyToManyField(
        StepikUser, related_name="authored_courses", blank=True
    )
    instructors = models.ManyToManyField(
        StepikUser, related_name="instructed_courses", blank=True
    )
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-learners_count"]

    def __str__(self):
        return self.title


class Review(ExternalEntityModel):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(
        StepikUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reviews",
    )
    score = models.IntegerField()
    text = models.TextField(blank=True)
    create_date = models.DateTimeField(null=True, blank=True)
    update_date = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-create_date"]

    def __str__(self):
        return f"Отзыв {self.external_id} на курс '{self.course.title}'"
