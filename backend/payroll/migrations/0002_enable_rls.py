from django.db import migrations

from accounts.rls import disable_rls, enable_rls

TABLES = ["payroll_salarystructure", "payroll_salarycomponent"]


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=enable_rls(table), reverse_sql=disable_rls(table))
        for table in TABLES
    ]
