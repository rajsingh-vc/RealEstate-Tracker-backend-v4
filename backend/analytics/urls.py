from django.urls import path

from .views import AIAssistantView, DashboardSummaryView, DelayPredictionView, DepartmentStatsView

urlpatterns = [
    path("analytics/department-stats/", DepartmentStatsView.as_view(), name="department-stats"),
    path("analytics/delay-predictions/", DelayPredictionView.as_view(), name="delay-predictions"),
    path("analytics/ai-assistant/", AIAssistantView.as_view(), name="ai-assistant"),
    path("analytics/dashboard-summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]
