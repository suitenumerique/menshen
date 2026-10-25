from django.conf import settings
from django.db import migrations, models


def hash_exchanged_tokens(apps, schema_editor):
    """Hash existing plaintext exchanged tokens."""
    import hmac
    from hashlib import sha256

    ExchangedToken = apps.get_model("token_exchange", "ExchangedToken")

    def hash_token(raw_token: str) -> str:
        key = settings.TOKEN_EXCHANGE_TOKEN_HASH_KEY or settings.SECRET_KEY
        if isinstance(key, str):
            key = key.encode()
        return hmac.new(key, raw_token.encode(), sha256).hexdigest()

    for token in ExchangedToken.objects.iterator():
        update_fields = []
        if token.token and len(token.token) != 64:
            token.token = hash_token(token.token)
            update_fields.append("token")
        if token.actor_token and len(token.actor_token) != 64:
            token.actor_token = hash_token(token.actor_token)
            update_fields.append("actor_token")
        elif token.actor_token == "":
            token.actor_token = None
            update_fields.append("actor_token")
        if update_fields:
            token.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('token_exchange', '0005_alter_exchangedtoken_subject_token_jti'),
    ]

    operations = [
        # Hash existing plaintext tokens while the field still allows long values
        # (JWTs exceed the 64-character target length).
        migrations.RunPython(hash_exchanged_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='exchangedtoken',
            name='actor_token',
            field=models.CharField(blank=True, default=None, help_text='HMAC-SHA256 hash of the actor token for delegation (RFC 8693)', max_length=64, null=True, verbose_name='Actor Token'),
        ),
        migrations.AlterField(
            model_name='exchangedtoken',
            name='token',
            field=models.CharField(db_index=True, help_text='HMAC-SHA256 hash of the actual token string (opaque or JWT)', max_length=64, unique=True, verbose_name='Token'),
        ),
    ]
