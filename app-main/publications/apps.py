from django.apps import AppConfig


class PublicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'publications'

    def ready(self):
        # Role groups at every CAS login (publications/roles.py).
        from django_cas_ng.signals import cas_user_authenticated

        from .roles import cas_user_authenticated_handler
        cas_user_authenticated.connect(
            cas_user_authenticated_handler, dispatch_uid='publications.roles.cas_login')
