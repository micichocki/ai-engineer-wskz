from enum import StrEnum


class Department(StrEnum):
    """Allowed recipients. The value is the mailbox address."""

    HUMAN_RESOURCES = "human-resources@example.com"
    HELP_DESK = "help-desk@example.com"
    IT = "it@example.com"
    KADRY = "kadry@example.com"
    OTHER = "other@example.com"


# Single source of truth for what each department handles: used as the decision
# model's criteria and in the agent prompt.
DESCRIPTIONS: dict[Department, str] = {
    Department.HUMAN_RESOURCES: (
        "People and their development: recruitment and candidates, onboarding, training and "
        "courses, career, promotion and performance reviews, conflicts, complaints and "
        "mistreatment at work."
    ),
    Department.HELP_DESK: (
        "Something the employee already uses has stopped working or works badly: any device, "
        "program, account, password or connection that is broken, blocked or failing."
    ),
    Department.IT: (
        "Something new or changed is needed from IT administrators: new accounts, access rights "
        "and permissions, installing or buying software and hardware, changes to servers, "
        "network or infrastructure."
    ),
    Department.KADRY: (
        "Formal employment paperwork and pay: any kind of leave or absence, salary, bonuses and "
        "payslips, tax forms, contracts and their changes, personal data, certificates issued "
        "by the employer."
    ),
    Department.OTHER: (
        "Anything that is not a matter for the four departments above, and text with no "
        "clear request."
    ),
}
