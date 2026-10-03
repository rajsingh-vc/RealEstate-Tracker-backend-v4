"""
ActivityNotificationMiddleware — the generic "whatever the user performs any
function on the website the SuperAdmin should get notified" hook.

Rather than editing every ViewSet in every app to call notify(), this
middleware watches every API request centrally: after any authenticated,
non-superadmin user successfully creates/updates/deletes something anywhere
under /api/, it fires one Notification per SuperAdmin describing what
happened. That keeps the feature working automatically for new endpoints
added later, without every view needing to know notifications exist.

If a specific action needs a nicer, hand-written message (e.g. "accepted
their invitation"), that's still created explicitly at the call site (see
accounts/views.py AcceptInvitationView) — those are separate Notification
rows layered on top of, not instead of, this middleware.
"""
import re

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

VERB_BY_METHOD = {
    "POST": "created",
    "PUT": "updated",
    "PATCH": "updated",
    "DELETE": "deleted",
}

# Paths that shouldn't generate activity notifications: auth flows (login,
# invite accept, token refresh — noisy / not meaningful "actions"), and the
# notifications endpoints themselves (mark_read etc. would otherwise spam
# every SuperAdmin every time someone reads their own notifications).
EXEMPT_PATH_PREFIXES = (
    "/api/auth/",
    "/api/notifications/",
    "/admin/",
)

# Trailing path segments that are actions/verbs rather than resource names —
# skipped when picking which segment names the resource, so e.g.
# /api/tasks/14/checklist/22/toggle/ resolves to "checklist item", not
# "toggle".
NON_RESOURCE_SEGMENTS = {"toggle", "resend", "mark_read", "mark_all_read", "unread_count"}

# A few resource words that don't singularize correctly by just stripping a
# trailing "s" (naive singularization otherwise used for everything else).
SINGULAR_OVERRIDES = {
    "entities": "entity",
    "companies": "company",
    "categories": "category",
    "subcategories": "subcategory",
}


def _singularize(word):
    word = word.replace("-", " ").replace("_", " ")
    if word in SINGULAR_OVERRIDES:
        return SINGULAR_OVERRIDES[word]
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _article_for(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def _resource_label(path):
    """/api/tasks/14/comments/ -> 'comment'; /api/projects/ -> 'project'."""
    segments = [s for s in path.strip("/").split("/") if s and s != "api"]
    segments = [s for s in segments if not s.isdigit() and s.lower() not in NON_RESOURCE_SEGMENTS]
    if not segments:
        return "item"
    return _singularize(segments[-1].lower())


class ActivityNotificationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_notify(request, response)
        except Exception:
            # Never let notification bookkeeping break the actual request.
            import logging
            logging.getLogger(__name__).exception("ActivityNotificationMiddleware failed")
        return response

    def _maybe_notify(self, request, response):
        if request.method not in MUTATING_METHODS:
            return
        if not (200 <= response.status_code < 300):
            return
        path = request.path
        if not path.startswith("/api/"):
            return
        if any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
            return

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return

        from .utils import notify_superadmins

        verb = VERB_BY_METHOD[request.method]
        resource = _resource_label(path)
        article = _article_for(resource)
        actor_name = user.name or user.username

        notify_superadmins(
            verb=f"{verb} {article} {resource}",
            actor=user,
            description=f"{actor_name} {verb} {article} {resource}.",
            target_url="",
        )
