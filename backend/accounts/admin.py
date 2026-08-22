from django.contrib import admin

from .models import BankDetail, Company, EmployeeProfile, User

admin.site.register(Company)
admin.site.register(User)
admin.site.register(EmployeeProfile)
admin.site.register(BankDetail)
