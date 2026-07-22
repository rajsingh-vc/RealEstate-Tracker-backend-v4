from rest_framework.routers import DefaultRouter

from .views import ComplianceItemViewSet

router = DefaultRouter()
router.register("compliance-items", ComplianceItemViewSet, basename="compliance-item")

urlpatterns = router.urls
