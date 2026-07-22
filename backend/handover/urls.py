from rest_framework.routers import DefaultRouter

from .views import HandoverUnitViewSet

router = DefaultRouter()
router.register("handover-units", HandoverUnitViewSet, basename="handover-unit")

urlpatterns = router.urls
