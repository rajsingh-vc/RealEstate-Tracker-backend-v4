from rest_framework.routers import DefaultRouter

from .views import CompanyViewSet, EntityViewSet, EscalationRuleViewSet, OrganizationViewSet

router = DefaultRouter()
router.register("escalation-rules", EscalationRuleViewSet, basename="escalation-rule")
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("companies", CompanyViewSet, basename="company")
router.register("entities", EntityViewSet, basename="entity")

urlpatterns = router.urls