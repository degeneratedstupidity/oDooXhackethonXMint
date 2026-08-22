from rest_framework.routers import DefaultRouter

from .views import TimeOffRequestViewSet, TimeOffTypeViewSet

router = DefaultRouter()
router.register("time-off-types", TimeOffTypeViewSet, basename="time-off-type")
router.register("time-off", TimeOffRequestViewSet, basename="time-off")

urlpatterns = router.urls
