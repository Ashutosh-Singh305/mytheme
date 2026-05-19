from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from crm.models import AuditModel

User = get_user_model()


class Report(AuditModel):
    TABULAR, SUMMARY, MATRIX = "tabular", "summary", "matrix"
    VIEW_CHOICES = [
        (TABULAR, "Tabular"),
        (SUMMARY, "Summary (Grouped)"),
        (MATRIX, "Matrix"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports")
    base_model = models.CharField(max_length=120)      # "app_label.ModelName"
    view_type = models.CharField(max_length=16, choices=VIEW_CHOICES, default=SUMMARY)
    spec = models.JSONField(default=dict)              # normalized spec
    limit = models.PositiveIntegerField(default=5000)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-modified_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("reports:detail", args=[self.slug])

    def get_run_url(self):
        return reverse("reports:run", args=[self.slug])
