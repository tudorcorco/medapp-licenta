

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_wallet_card_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='beneficiary_birth_date',
            field=models.DateField(blank=True, null=True, verbose_name='Data nașterii beneficiar'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='beneficiary_cnp',
            field=models.CharField(blank=True, default='', max_length=13, verbose_name='CNP beneficiar'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='beneficiary_name',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Nume beneficiar'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='beneficiary_phone',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Telefon beneficiar'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='beneficiary_relation',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Relație (copil, părinte, etc.)'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='is_for_other',
            field=models.BooleanField(default=False, verbose_name='Programare pentru altcineva'),
        ),
        migrations.AlterField(
            model_name='appointment',
            name='payment_method',
            field=models.CharField(blank=True, choices=[('CASH', 'Cash'), ('CARD_ONLINE', 'Card online'), ('CNAS', 'Decontat CNAS'), ('WALLET', 'Wallet MedApp')], default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='payment',
            name='method',
            field=models.CharField(choices=[('CASH', 'Cash'), ('CARD_ONLINE', 'Card online'), ('CNAS', 'Decontat CNAS'), ('WALLET', 'Wallet MedApp')], max_length=20),
        ),
    ]
