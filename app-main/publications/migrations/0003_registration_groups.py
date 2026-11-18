"""Create the three role groups of the registration plan (Phase 1b, roadmap FA-R54).

Adds rows only: the groups dtu_user, artek_staff and artek_editor and their links to
existing permissions. No user is added to a group here (that happens at every CAS login,
publications/roles.py), and no existing row is changed. The reverse removes exactly these
three groups (and with them their permission links); the permissions stay.
"""
from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Group name -> permission codenames (all in app 'publications').
GROUP_PERMISSIONS = {
    'dtu_user': [
        'edit_own_publication',
        'add_person',
        'edit_own_person',
        'add_feature',
        'edit_own_feature',
        'delete_own_feature',
    ],
    'artek_staff': [
        'add_publication',
        'delete_own_publication',
    ],
    'artek_editor': [
        'add_publication',
        'change_publication',
        'delete_publication',
        'verify_publication',
        'change_person',
        'change_feature',
        'delete_feature',
    ],
}


def create_groups(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    # Permissions (default and Meta.permissions) are normally created by post_migrate, which
    # has not run yet on an empty database. Create the missing ones now from the historical
    # models. create_permissions() skips an app config without models_module, so it is given
    # the real app config; it looks up the historical one through `apps` itself.
    create_permissions(global_apps.get_app_config('publications'), verbosity=0,
                       using=db_alias, apps=apps)

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    for group_name, codenames in GROUP_PERMISSIONS.items():
        permissions = []
        for codename in codenames:
            try:
                permissions.append(Permission.objects.using(db_alias).get(
                    content_type__app_label='publications', codename=codename))
            except Permission.DoesNotExist:
                raise RuntimeError(
                    f'Permission publications.{codename} for group {group_name} does not exist')
        group, _ = Group.objects.using(db_alias).get_or_create(name=group_name)
        group.permissions.add(*permissions)


def remove_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).filter(
        name__in=list(GROUP_PERMISSIONS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('publications', '0002_alter_feature_created_date_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
