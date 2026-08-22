from django.contrib import admin

from .models import PublicHoliday, TimeOffRequest, TimeOffType

admin.site.register(TimeOffType)
admin.site.register(TimeOffRequest)
admin.site.register(PublicHoliday)
