from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True, allow_unicode=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")

    def clean(self):
        if self.parent_id is None:
            return
        ancestor = self.parent
        visited = set()
        while ancestor is not None:
            if ancestor.pk == self.pk or ancestor.pk in visited:
                raise ValidationError({"parent": "A category cannot be its own ancestor"})
            visited.add(ancestor.pk)
            ancestor = ancestor.parent

    def __str__(self):
        return self.name
