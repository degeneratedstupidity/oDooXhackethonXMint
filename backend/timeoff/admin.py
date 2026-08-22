from django.contrib import admin

from .models import TimeOffRequest, TimeOffType

admin.site.register(TimeOffType)
admin.site.register(TimeOffRequest)
