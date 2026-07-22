from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet, TowerViewSet, FloorViewSet, UnitViewSet, StatusViewSet



router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("towers", TowerViewSet, basename="tower")
router.register("floors", FloorViewSet, basename="floor")
router.register("units", UnitViewSet, basename="unit")
router.register('statuses', StatusViewSet, basename='status')  # new

urlpatterns = router.urls