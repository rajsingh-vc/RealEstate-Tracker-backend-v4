from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, SubCategoryViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("subcategories", SubCategoryViewSet, basename="subcategory")

urlpatterns = router.urls
