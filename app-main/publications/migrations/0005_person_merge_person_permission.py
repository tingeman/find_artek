"""Permission ``publications.merge_person`` for the artek_editor group (plan release-2026-7 T7,
roadmap FA-R66).

Holders see the duplicate markers of person links and may confirm (later also merge) persons.

Adds rows only: the permission (if post_migrate hasn't created it yet) and its link to the
group artek_editor. No publication, person or link row is touched, and no user is changed.
The reverse removes the group link and the permission row (and with it any other link to it).
"""
from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

CODENAME = 'merge_person'
GROUP = 'artek_editor'


def grant(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    # As in 0003_registration_groups: post_migrate creates Meta.permissions only after all
    # migrations, so create the missing ones now from the historical models.
    create_permissions(global_apps.get_app_config('publications'), verbosity=0,
                       using=db_alias, apps=apps)
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    permission = Permission.objects.using(db_alias).get(
        content_type__app_label='publications', codename=CODENAME)
    # 0003 creates the group; get_or_create in case it was removed by hand.
    group, _ = Group.objects.using(db_alias).get_or_create(name=GROUP)
    group.permissions.add(permission)


def revoke(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    permissions = Permission.objects.using(db_alias).filter(
        content_type__app_label='publications', codename=CODENAME)
    for group in Group.objects.using(db_alias).filter(name=GROUP):
        group.permissions.remove(*permissions)
    permissions.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('publications', '0004_publication_confidential'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='person',
            options={'permissions': (('edit_own_person', 'Can edit own person'),
                                     ('delete_own_person', 'Can delete own person'),
                                     ('merge_person', 'Can confirm and merge persons'))},
        ),
        migrations.RunPython(grant, revoke),
    ]
