from app.departments import DESCRIPTIONS, Department


def test_addresses_match_the_task_list():
    assert {d.value for d in Department} == {
        "human-resources@example.com",
        "help-desk@example.com",
        "it@example.com",
        "kadry@example.com",
        "other@example.com",
    }


def test_every_department_has_a_description():
    assert set(DESCRIPTIONS) == set(Department)
    assert all(DESCRIPTIONS.values())
