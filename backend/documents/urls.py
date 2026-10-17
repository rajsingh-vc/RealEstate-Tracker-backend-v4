from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DocumentViewSet,
    ScheduleImportViewSet,
    ScheduleVersionViewSet,
    DigitalTwinTaskMappingViewSet,
)

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")
router.register("schedule-imports", ScheduleImportViewSet, basename="schedule-import")
router.register("schedule-versions", ScheduleVersionViewSet, basename="schedule-version")
router.register("digital-twin-mappings", DigitalTwinTaskMappingViewSet, basename="digital-twin-mapping")

urlpatterns = [
    path('', include(router.urls)),
]