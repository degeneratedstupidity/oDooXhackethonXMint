from django.db import migrations, models
import django.db.models.deletion

from accounts.rls import disable_rls, enable_rls

TABLE = "timeoff_publicholiday"


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("timeoff", "0002_enable_rls"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicHoliday",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("date", models.DateField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.company")),
            ],
            options={"ordering": ["date"]},
        ),
        migrations.AddConstraint(
            model_name="publicholiday",
            constraint=models.UniqueConstraint(
                fields=("company", "date"), name="one_holiday_per_company_per_date"
            ),
        ),
        migrations.RunSQL(sql=enable_rls(TABLE), reverse_sql=disable_rls(TABLE)),
    ]
