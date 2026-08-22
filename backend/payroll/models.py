from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models, transaction

from accounts.models import TenantScopedModel, User


class ComponentCode(models.TextChoices):
    """The salary components named in the specification, in the order they are displayed."""

    BASIC = "basic", "Basic Salary"
    HRA = "hra", "House Rent Allowance"
    STANDARD = "standard", "Standard Allowance"
    PERFORMANCE_BONUS = "performance_bonus", "Performance Bonus"
    LTA = "lta", "Leave Travel Allowance"
    FIXED = "fixed", "Fixed Allowance"


class ComputationType(models.TextChoices):
    PERCENT_OF_WAGE = "percent_of_wage", "Percentage of wage"
    PERCENT_OF_BASIC = "percent_of_basic", "Percentage of basic"
    FIXED_AMOUNT = "fixed_amount", "Fixed amount"
    REMAINDER = "remainder", "Remainder of wage"


# The defaults from the worked example in the specification: on a 50,000 wage, Basic is
# 50% (25,000) and HRA is 50% of Basic (12,500). Fixed Allowance absorbs whatever is left
# so the components always sum to exactly the wage.
DEFAULT_COMPONENTS = [
    (ComponentCode.BASIC, ComputationType.PERCENT_OF_WAGE, Decimal("50")),
    (ComponentCode.HRA, ComputationType.PERCENT_OF_BASIC, Decimal("50")),
    (ComponentCode.STANDARD, ComputationType.FIXED_AMOUNT, Decimal("4167")),
    (ComponentCode.PERFORMANCE_BONUS, ComputationType.PERCENT_OF_BASIC, Decimal("8.33")),
    (ComponentCode.LTA, ComputationType.PERCENT_OF_BASIC, Decimal("8.33")),
    (ComponentCode.FIXED, ComputationType.REMAINDER, Decimal("0")),
]


class SalaryStructure(TenantScopedModel):
    """An employee's wage and the statutory rates applied to it.

    Salary information is Admin-only throughout the API — HR Officers administer people
    and leave, but not pay.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="salary")

    monthly_wage = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    working_days_per_week = models.PositiveSmallIntegerField(default=5)
    break_time_hours = models.DecimalField(max_digits=4, decimal_places=2, default=1)

    # Statutory rates, configurable per employee but defaulted to the Indian norms in
    # the specification.
    pf_employee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    pf_employer_percent = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    professional_tax = models.DecimalField(max_digits=8, decimal_places=2, default=200)

    def __str__(self):
        return f"Salary of {self.user.full_name}"

    @property
    def yearly_wage(self):
        return self.monthly_wage * 12

    @property
    def pf_employee_amount(self):
        """Provident fund is calculated on basic salary, not on the full wage."""
        basic = self.components.filter(code=ComponentCode.BASIC).first()
        base = basic.amount if basic else Decimal("0")
        return (base * self.pf_employee_percent / 100).quantize(Decimal("0.01"))

    @property
    def pf_employer_amount(self):
        basic = self.components.filter(code=ComponentCode.BASIC).first()
        base = basic.amount if basic else Decimal("0")
        return (base * self.pf_employer_percent / 100).quantize(Decimal("0.01"))

    @transaction.atomic
    def recompute(self):
        """Recalculate every component from the wage.

        Called whenever the wage or a component definition changes, so the stored amounts
        can never drift from the wage they are derived from.

        Order matters: percentages of basic need basic resolved first, and the remainder
        component needs everything else resolved before it can absorb what is left.
        """
        components = {component.code: component for component in self.components.all()}

        basic = components.get(ComponentCode.BASIC)
        basic_amount = Decimal("0")
        if basic:
            basic_amount = basic.compute(self.monthly_wage, Decimal("0"))
            basic.amount = basic_amount
            basic.save(update_fields=["amount"])

        allocated = basic_amount
        remainder_components = []

        for code, component in components.items():
            if code == ComponentCode.BASIC:
                continue
            if component.computation_type == ComputationType.REMAINDER:
                remainder_components.append(component)
                continue
            component.amount = component.compute(self.monthly_wage, basic_amount)
            component.save(update_fields=["amount"])
            allocated += component.amount

        # Whatever the wage has left over, after every other component is satisfied.
        # Never negative: an over-allocated structure leaves this at zero and is caught
        # by the serializer's validation instead.
        leftover = max(Decimal("0"), self.monthly_wage - allocated)
        for component in remainder_components:
            component.amount = leftover
            component.save(update_fields=["amount"])
            leftover = Decimal("0")

    @transaction.atomic
    def apply_default_components(self):
        """Give a new structure the standard component set."""
        for code, computation_type, value in DEFAULT_COMPONENTS:
            SalaryComponent.objects.get_or_create(
                company=self.company,
                structure=self,
                code=code,
                defaults={"computation_type": computation_type, "value": value},
            )
        self.recompute()


class SalaryComponent(TenantScopedModel):
    """One line of the salary structure, e.g. Basic at 50% of wage."""

    structure = models.ForeignKey(
        SalaryStructure, on_delete=models.CASCADE, related_name="components"
    )
    code = models.CharField(max_length=32, choices=ComponentCode.choices)
    computation_type = models.CharField(max_length=20, choices=ComputationType.choices)
    # A percentage or a rupee amount, depending on computation_type.
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # The resolved monthly amount, kept in sync by SalaryStructure.recompute().
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "code"], name="one_component_per_code_per_structure"
            )
        ]

    def __str__(self):
        return f"{self.get_code_display()}: {self.amount}"

    def compute(self, wage, basic_amount):
        if self.computation_type == ComputationType.PERCENT_OF_WAGE:
            return (wage * self.value / 100).quantize(Decimal("0.01"))
        if self.computation_type == ComputationType.PERCENT_OF_BASIC:
            return (basic_amount * self.value / 100).quantize(Decimal("0.01"))
        if self.computation_type == ComputationType.FIXED_AMOUNT:
            return self.value.quantize(Decimal("0.01"))
        # REMAINDER is resolved by the structure, which alone knows the total allocated.
        return Decimal("0")
