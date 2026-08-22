from django.db import migrations

from accounts.rls import disable_rls, enable_rls

TABLE = "attendance_attendance"


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=enable_rls(TABLE), reverse_sql=disable_rls(TABLE)),
    ]
