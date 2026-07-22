from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from tasks.models import Task

from .services import delay_predictions, department_stats, generate_ai_response


class DepartmentStatsView(APIView):
    """GET /api/analytics/department-stats/ — backs the `departmentStats` chart
    data used on src/pages/Reports.tsx and src/pages/Dashboard.tsx."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(department_stats())


class DelayPredictionView(APIView):
    """GET /api/analytics/delay-predictions/ — backs src/pages/DelayPrediction.tsx."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(delay_predictions())


class AIAssistantView(APIView):
    """POST /api/analytics/ai-assistant/ {message} -> {response}
    backs src/pages/AIAssistant.tsx."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "")
        if not message.strip():
            return Response({"message": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"response": generate_ai_response(message)})


class DashboardSummaryView(APIView):
    """GET /api/analytics/dashboard-summary/ — lightweight portfolio-wide counters
    for the stat cards at the top of src/pages/Dashboard.tsx."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tasks = Task.objects.all()
        projects = Project.objects.all()
        return Response(
            {
                "totalProjects": projects.count(),
                "activeProjects": projects.filter(status="active").count(),
                "totalTasks": tasks.count(),
                "completedTasks": tasks.filter(status="completed").count(),
                "delayedTasks": tasks.filter(status="delayed").count(),
                "blockedTasks": tasks.filter(status="blocked").count(),
                "criticalPathTasks": tasks.filter(critical_path=True).exclude(status="completed").count(),
            }
        )


def get_queryset(self):
    user = self.request.user
    if user.is_superuser or user.role == 'SuperAdmin':
        return self.queryset
    if user.company:
        return self.queryset.filter(company=user.company)
    return self.queryset.none()