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
        "Recruitment, onboarding, training, career development, performance reviews, "
        "workplace conflicts and complaints about colleagues."
    ),
    Department.HELP_DESK: (
        "Something the employee uses is broken or not working: computer, printer, "
        "password, e-mail, VPN, application errors."
    ),
    Department.IT: (
        "Requests to IT administrators: new accounts and access rights, software and "
        "hardware orders, servers, network and infrastructure changes."
    ),
    Department.KADRY: (
        "Personnel administration: leave and vacation requests, sick leave, payroll, "
        "employment contracts, certificates of employment."
    ),
    Department.OTHER: "Anything that does not clearly belong to the other departments.",
}
