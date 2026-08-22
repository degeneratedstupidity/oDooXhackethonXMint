from django.contrib import admin

from .models import SalaryComponent, SalaryStructure

admin.site.register(SalaryStructure)
admin.site.register(SalaryComponent)
