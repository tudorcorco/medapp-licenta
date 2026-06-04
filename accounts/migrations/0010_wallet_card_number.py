

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_appointment_amount_paid_appointment_cnas_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='card_number',
            field=models.CharField(blank=True, default='', max_length=25, unique=True),
        ),
    ]
