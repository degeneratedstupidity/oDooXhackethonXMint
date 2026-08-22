from rest_framework.routers import DefaultRouter

from .views import SalaryStructureViewSet

router = DefaultRouter()
router.register("salary", SalaryStructureViewSet, basename="salary")

urlpatterns = router.urls
