from decimal import Decimal

from rest_framework import serializers

from .models import ComponentCode, ComputationType, SalaryComponent, SalaryStructure


class SalaryComponentSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_code_display", read_only=True)

    class Meta:
        model = SalaryComponent
        fields = ["id", "code", "label", "computation_type", "value", "amount"]
        read_only_fields = ["id", "code", "label", "amount"]


class SalaryStructureSerializer(serializers.ModelSerializer):
    components = SalaryComponentSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source="user.full_name", read_only=True)
    yearly_wage = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    pf_employee_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    pf_employer_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = SalaryStructure
        fields = [
            "id",
            "user",
            "employee_name",
            "monthly_wage",
            "yearly_wage",
            "working_days_per_week",
            "break_time_hours",
            "pf_employee_percent",
            "pf_employer_percent",
            "professional_tax",
            "pf_employee_amount",
            "pf_employer_amount",
            "components",
        ]
        read_only_fields = ["id", "user", "employee_name"]

    def validate_monthly_wage(self, value):
        if value < 0:
            raise serializers.ValidationError("Wage cannot be negative.")
        return value

    def validate_working_days_per_week(self, value):
        if not 1 <= value <= 7:
            raise serializers.ValidationError("Working days must be between 1 and 7.")
        return value

    def validate(self, attrs):
        """The specification's hard rule: components must never exceed the wage.

        Checked against the wage being saved, using the structure's current component
        definitions, so an unaffordable wage cut is rejected rather than silently
        producing a zero Fixed Allowance.
        """
        wage = attrs.get("monthly_wage", getattr(self.instance, "monthly_wage", Decimal("0")))
        if not self.instance:
            return attrs

        basic = self.instance.components.filter(code=ComponentCode.BASIC).first()
        basic_amount = basic.compute(wage, Decimal("0")) if basic else Decimal("0")

        allocated = Decimal("0")
        for component in self.instance.components.all():
            if component.computation_type == ComputationType.REMAINDER:
                continue
            allocated += component.compute(wage, basic_amount)

        if allocated > wage:
            raise serializers.ValidationError(
                f"Salary components total ₹{allocated:,.2f}, which is more than the "
                f"₹{wage:,.2f} wage. Lower a component before reducing the wage."
            )
        return attrs

    def update(self, instance, validated_data):
        structure = super().update(instance, validated_data)
        # Amounts are derived, so they are refreshed on every change to the wage.
        structure.recompute()
        return structure
