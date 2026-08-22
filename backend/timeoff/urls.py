from rest_framework.routers import DefaultRouter

from .views import PublicHolidayViewSet, TimeOffRequestViewSet, TimeOffTypeViewSet

router = DefaultRouter()
router.register("time-off-types", TimeOffTypeViewSet, basename="time-off-type")
router.register("public-holidays", PublicHolidayViewSet, basename="public-holiday")
router.register("time-off", TimeOffRequestViewSet, basename="time-off")

urlpatterns = router.urls
