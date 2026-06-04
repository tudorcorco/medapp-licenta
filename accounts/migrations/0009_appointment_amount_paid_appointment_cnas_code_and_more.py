

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_alter_auditlog_action_rating'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='amount_paid',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='appointment',
            name='cnas_code',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='Cod validare CNAS'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='cnas_covered',
            field=models.BooleanField(default=False, verbose_name='Decontat CNAS'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='icd10_code',
            field=models.CharField(blank=True, default='', max_length=10, verbose_name='Cod ICD-10'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='is_no_show',
            field=models.BooleanField(default=False, verbose_name='Neprezentare'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='payment_method',
            field=models.CharField(blank=True, choices=[('CASH', 'Cash'), ('CARD_POS', 'Card POS'), ('ONLINE', 'Online (Stripe)'), ('CNAS', 'Decontat CNAS'), ('WALLET', 'Wallet MedApp')], default='', max_length=20),
        ),
        migrations.AddField(
            model_name='appointment',
            name='referral_serial',
            field=models.CharField(blank=True, default='', max_length=30, verbose_name='Serie bilet trimitere'),
        ),
        migrations.AddField(
            model_name='patientprofile',
            name='health_card_serial',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Serie card sănătate'),
        ),
        migrations.AddField(
            model_name='patientprofile',
            name='is_insured',
            field=models.BooleanField(default=False, verbose_name='Asigurat CNAS'),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('LOGIN_SUCCESS', 'Autentificare reușită'), ('LOGIN_FAILED', 'Autentificare eșuată'), ('LOGOUT', 'Deconectare'), ('REGISTER', 'Înregistrare cont nou'), ('APPT_CREATED', 'Programare creată'), ('APPT_APPROVED', 'Programare aprobată'), ('APPT_COMPLETED', 'Consultație finalizată'), ('APPT_DELETED', 'Programare ștearsă'), ('APPT_NO_SHOW', 'Neprezentare marcată'), ('PROFILE_UPDATED', 'Profil actualizat'), ('PRESCRIPTION_CREATED', 'Rețetă creată'), ('PASSWORD_CHANGED', 'Parolă schimbată'), ('PATIENT_RECORD_VIEWED', 'Fișă pacient vizualizată'), ('AVAILABILITY_CHANGED', 'Disponibilitate schimbată'), ('RATING_GIVEN', 'Evaluare acordată'), ('GDPR_EXPORT', 'Export date GDPR'), ('PAYMENT_CREATED', 'Plată înregistrată'), ('CNAS_GENERATED', 'Cod CNAS generat'), ('WALLET_TOPUP', 'Wallet reîncărcat')], max_length=50),
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('method', models.CharField(choices=[('CASH', 'Cash'), ('CARD_POS', 'Card POS'), ('ONLINE', 'Online (Stripe)'), ('CNAS', 'Decontat CNAS'), ('WALLET', 'Wallet MedApp')], max_length=20)),
                ('status', models.CharField(choices=[('PENDING', 'În așteptare'), ('COMPLETED', 'Finalizat'), ('FAILED', 'Eșuat'), ('REFUNDED', 'Rambursat')], default='PENDING', max_length=20)),
                ('stripe_id', models.CharField(blank=True, default='', max_length=100)),
                ('reference', models.CharField(blank=True, default='', max_length=40)),
                ('note', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('appointment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='accounts.appointment')),
                ('beneficiary', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments_received', to=settings.AUTH_USER_MODEL)),
                ('payer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments_made', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Wallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
