"""Database routers for staging models."""


class StagingRouter:
    """Route staging_review models to the 'staging' database."""

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'staging_review':
            return 'staging'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'staging_review':
            return 'staging'
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Never migrate staging_review models on any database
        if app_label == 'staging_review':
            return False
        # Allow migrations for other apps on their appropriate databases
        if db == 'staging':
            # Prevent other apps from migrating on staging
            return False
        return None
