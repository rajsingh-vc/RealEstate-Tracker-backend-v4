from rest_framework import viewsets

from accounts.permissions import IsAdminOrCEO
from adminpanel.scoping import is_unrestricted, user_organization_ids

from .models import Category, SubCategory
from .serializers import CategoryListSerializer, CategorySerializer, SubCategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    """CRUD for "Categories". Same underlying rows as /api/towers/, exposed
    under /api/categories/ with category-shaped field names for the
    Category Management page."""

    queryset = Category.objects.select_related("project").prefetch_related("floors__units").all()
    permission_classes = [IsAdminOrCEO]
    filterset_fields = ["project"]
    search_fields = ["name"]

    def get_serializer_class(self):
        return CategorySerializer if self.action == "retrieve" else CategoryListSerializer

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)


class SubCategoryViewSet(viewsets.ModelViewSet):
    """CRUD for "Sub Categories". Same underlying rows as /api/floors/,
    exposed under /api/subcategories/."""

    queryset = SubCategory.objects.select_related("tower", "project").prefetch_related("units").all()
    serializer_class = SubCategorySerializer
    permission_classes = [IsAdminOrCEO]
    filterset_fields = ["tower", "project"]
    search_fields = ["name"]

    def get_queryset(self):
        user = self.request.user
        if is_unrestricted(user):
            return self.queryset
        org_ids = user_organization_ids(user)
        if not org_ids:
            return self.queryset.none()
        return self.queryset.filter(project__organization_id__in=org_ids)
