from rest_framework.routers import DefaultRouter

from .views import SocietyViewSet

router = DefaultRouter()
router.register("societies", SocietyViewSet, basename="society")

urlpatterns = router.urls
