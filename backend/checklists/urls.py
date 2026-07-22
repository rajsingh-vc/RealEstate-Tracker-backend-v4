from rest_framework.routers import DefaultRouter

from .views import ChecklistTemplateViewSet, ChecklistViewSet, SubTaskViewSet

router = DefaultRouter()
router.register("checklist-templates", ChecklistTemplateViewSet, basename="checklist-template")
router.register("checklists", ChecklistViewSet, basename="checklist")
router.register("subtasks", SubTaskViewSet, basename="subtask")

urlpatterns = router.urls