

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_alter_auditlog_action_prescription'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorprofile',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/doctors/'),
        ),
        migrations.AlterField(
            model_name='prescription',
            name='medication',
            field=models.TextField(),
        ),
    ]
