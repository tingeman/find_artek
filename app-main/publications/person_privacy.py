"""Who may see which person data (plan "registration" T13, decided 2026-11-18).

One place for the rules, used by the person page (PersonView) and the API serializers:

- ``id_number`` (study number or employee ID): only logged-in users.
- ``email``: logged-in users always; anonymous users only when the person is not a
  student (``Person.is_student()``). Staff e-mails are institutional and stay public.
- The contact fields in ``CONTACT_FIELDS`` are not shown or editable anywhere (pages,
  forms, API, admin). The columns stay in the database until roadmap FA-R72.
"""

# Person fields that are no longer shown or editable anywhere.
CONTACT_FIELDS = (
    'phone', 'cell_phone', 'address_1', 'address_2', 'zip_code', 'town', 'state',
    'country', 'homepage',
)


def _is_logged_in(user):
    return bool(getattr(user, 'is_authenticated', False))


def can_view_id_number(user):
    """True if ``user`` (a User, AnonymousUser or None) may see Person.id_number."""
    return _is_logged_in(user)


def can_view_email(user, person):
    """True if ``user`` may see ``person.email``: logged-in users, or anyone for a
    person who is not a student."""
    return _is_logged_in(user) or not person.is_student()


def visible_id_number(user, person):
    """person.id_number, or None if empty or not visible to ``user``."""
    if not can_view_id_number(user):
        return None
    return person.id_number or None


def visible_email(user, person):
    """person.email, or None if empty or not visible to ``user``."""
    if not can_view_email(user, person):
        return None
    return person.email or None
