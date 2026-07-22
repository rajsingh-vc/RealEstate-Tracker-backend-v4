from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("projects.urls")),
    path("api/", include("tasks.urls")),
    path("api/", include("hurdles.urls")),
    path("api/", include("resources.urls")),
    path("api/", include("checklists.urls")),
    path("api/", include("compliance.urls")),
    path("api/", include("handover.urls")),
    path("api/", include("society.urls")),
    path("api/", include("documents.urls")),
    path("api/", include("adminpanel.urls")),
    path("api/", include("analytics.urls")),
    path("api/", include("categorymanagement.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
