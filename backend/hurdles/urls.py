from rest_framework.routers import DefaultRouter

from .views import HurdleViewSet

router = DefaultRouter()
router.register("hurdles", HurdleViewSet, basename="hurdle")

urlpatterns = router.urls
