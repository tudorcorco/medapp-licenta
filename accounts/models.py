from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Count, Max
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class CustomUser(AbstractUser):
    is_patient = models.BooleanField(default=False)
    is_doctor  = models.BooleanField(default=False)
    is_admin   = models.BooleanField(default=False)

    def __str__(self):
        return self.username

    def get_role_label(self):
        if self.is_superuser or self.is_staff:
            return 'Admin'
        if self.is_doctor:
            return 'Medic'
        if self.is_patient:
            return 'Pacient'
        return 'Utilizator'


class PatientProfile(models.Model):
    user               = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='patient_profile')
    cnp                = models.CharField(max_length=13, blank=True, default='')
    birth_date         = models.DateField(null=True, blank=True)
    blood_type         = models.CharField(max_length=5, blank=True, default='')
    allergies          = models.TextField(blank=True, default='')
    phone              = models.CharField(max_length=20, blank=True, default='')
    is_insured         = models.BooleanField(default=False, verbose_name='Asigurat CNAS')
    health_card_serial = models.CharField(max_length=20, blank=True, default='', verbose_name='Serie card sănătate')

    def __str__(self):
        return f'Profil: {self.user.username}'


class DoctorProfile(models.Model):
    user             = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='doctor_profile')
    avatar           = models.ImageField(upload_to='avatars/doctors/', null=True, blank=True)
    specialization   = models.CharField(max_length=120, blank=True, default='')
    license_number   = models.CharField(max_length=50, blank=True, default='')
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    bio              = models.TextField(blank=True, default='')
    is_available     = models.BooleanField(default=True)

    def __str__(self):
        return f'Dr. {self.user.username}'

    def average_rating(self):
        ratings = self.user.ratings_received.all()
        if not ratings.exists():
            return None
        return round(sum(r.score for r in ratings) / ratings.count(), 1)

    def rating_count(self):
        return self.user.ratings_received.count()

    def performance_score(self):
        """
        Scor de performanță ponderat (0-100):
          50% - Calitate: media recenziilor (1-5 stele -> 0-100)
          30% - Fiabilitate: rata consultatii finalizate vs. total (fara no-show)
          20% - Volum: consultatiile acestui medic / max consultatii din clinica
        """
        appts     = self.user.appointments_as_doctor.all()
        total     = appts.count()
        completed = appts.filter(is_completed=True).count()
        no_show   = appts.filter(is_no_show=True).count()

        # 50% — Calitate (rating mediu -> 0-100)
        avg           = self.average_rating() or 0.0
        quality_score = (avg / 5.0) * 100

        # 30% — Fiabilitate (completed / (total - no_show))
        effective_total = total - no_show
        if effective_total > 0:
            reliability_score = (completed / effective_total) * 100
        else:
            reliability_score = 0.0

        # 20% — Volum relativ (fata de cel mai activ medic din clinica)
        max_completed = (
            self.__class__.objects.annotate(
                comp=Count('user__appointments_as_doctor',
                           filter=models.Q(user__appointments_as_doctor__is_completed=True))
            ).aggregate(m=Max('comp'))['m'] or 1
        )
        volume_score = (completed / max_completed) * 100

        score = (quality_score * 0.50) + (reliability_score * 0.30) + (volume_score * 0.20)
        return round(score, 1)


class Appointment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH        = 'CASH',        'Cash'
        CARD_ONLINE = 'CARD_ONLINE', 'Card online'
        CNAS        = 'CNAS',        'Decontat CNAS'
        WALLET      = 'WALLET',      'Wallet MedApp'

    patient      = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='appointments_as_patient')
    doctor       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='appointments_as_doctor')
    date_time    = models.DateTimeField()
    reason       = models.TextField(blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    is_no_show   = models.BooleanField(default=False, verbose_name='Neprezentare')
    created_at   = models.DateTimeField(auto_now_add=True)

    is_for_other           = models.BooleanField(default=False, verbose_name='Programare pentru altcineva')
    beneficiary_name       = models.CharField(max_length=100, blank=True, default='', verbose_name='Nume beneficiar')
    beneficiary_cnp        = models.CharField(max_length=13, blank=True, default='', verbose_name='CNP beneficiar')
    beneficiary_birth_date = models.DateField(null=True, blank=True, verbose_name='Data nasterii beneficiar')
    beneficiary_phone      = models.CharField(max_length=20, blank=True, default='', verbose_name='Telefon beneficiar')
    beneficiary_relation   = models.CharField(max_length=50, blank=True, default='', verbose_name='Relatie (copil, parinte, etc.)')

    referral_serial = models.CharField(max_length=30, blank=True, default='', verbose_name='Serie bilet trimitere')
    icd10_code      = models.CharField(max_length=10, blank=True, default='', verbose_name='Cod ICD-10')
    cnas_covered    = models.BooleanField(default=False, verbose_name='Decontat CNAS')
    cnas_code       = models.CharField(max_length=40, blank=True, default='', verbose_name='Cod validare CNAS')

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True, default='')
    amount_paid    = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        ordering = ['-date_time']

    def __str__(self):
        return f'{self.patient.username} -> Dr. {self.doctor.username} ({self.date_time.strftime("%Y-%m-%d %H:%M")})'

    def generate_cnas_code(self):
        return f'CNAS-{uuid.uuid4().hex[:12].upper()}'

    def get_patient_display_name(self):
        if self.is_for_other and self.beneficiary_name:
            return self.beneficiary_name
        return self.patient.get_full_name() or self.patient.username


class Prescription(models.Model):
    appointment  = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='prescription')
    doctor       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='prescriptions_written')
    patient      = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='prescriptions_received')
    diagnosis    = models.TextField(blank=True, default='')
    medication   = models.TextField()
    instructions = models.TextField(blank=True, default='')
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Reteta: {self.patient.username} de la Dr. {self.doctor.username}'


class Rating(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='rating')
    patient     = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ratings_given')
    doctor      = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ratings_received')
    score       = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment     = models.TextField(blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.patient.username} -> Dr. {self.doctor.username}: {self.score}★'


class Wallet(models.Model):
    user        = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    balance     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    card_number = models.CharField(max_length=25, unique=True, blank=True, default='')
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.card_number:
            import random
            while True:
                candidate = f'MED-{random.randint(1000,9999)}-{random.randint(1000,9999)}'
                if not Wallet.objects.filter(card_number=candidate).exists():
                    self.card_number = candidate
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Wallet {self.user.username}: {self.balance} RON [{self.card_number}]'


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING   = 'PENDING',   'In asteptare'
        COMPLETED = 'COMPLETED', 'Finalizat'
        FAILED    = 'FAILED',    'Esuat'
        REFUNDED  = 'REFUNDED',  'Rambursat'

    class Method(models.TextChoices):
        CASH        = 'CASH',        'Cash'
        CARD_ONLINE = 'CARD_ONLINE', 'Card online'
        ONLINE      = 'ONLINE',      'Online'
        CNAS        = 'CNAS',        'Decontat CNAS'
        WALLET      = 'WALLET',      'Wallet MedApp'

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='payments')
    payer       = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='payments_made')
    beneficiary = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='payments_received')
    amount      = models.DecimalField(max_digits=8, decimal_places=2)
    method      = models.CharField(max_length=20, choices=Method.choices)
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    stripe_id   = models.CharField(max_length=100, blank=True, default='')
    reference   = models.CharField(max_length=40, blank=True, default='')
    note        = models.TextField(blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Payment #{self.id} - {self.amount} RON - {self.method} - {self.status}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'PAY-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)


class WalletTransaction(models.Model):
    """Istoric detaliat al tuturor miscarilor din wallet (credit/debit)."""

    class TxType(models.TextChoices):
        TOPUP    = 'TOPUP',    'Reincarcare card'
        PAYMENT  = 'PAYMENT',  'Plata consultatie'
        CASHBACK = 'CASHBACK', 'Cashback 5% card online'
        TRANSFER = 'TRANSFER', 'Transfer (apartinat)'
        REFUND   = 'REFUND',   'Rambursare'

    wallet        = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    tx_type       = models.CharField(max_length=20, choices=TxType.choices)
    amount        = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    description   = models.CharField(max_length=200, blank=True, default='')
    reference     = models.CharField(max_length=40, blank=True, default='')
    appointment   = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='wallet_transactions')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.tx_type in ('TOPUP', 'CASHBACK', 'REFUND') else '-'
        return f'[{self.tx_type}] {sign}{self.amount} RON -> sold: {self.balance_after} RON'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'TX-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN_SUCCESS         = 'LOGIN_SUCCESS',         'Autentificare reusita'
        LOGIN_FAILED          = 'LOGIN_FAILED',          'Autentificare esuata'
        LOGOUT                = 'LOGOUT',                'Deconectare'
        REGISTER              = 'REGISTER',              'Inregistrare cont nou'
        APPT_CREATED          = 'APPT_CREATED',          'Programare creata'
        APPT_APPROVED         = 'APPT_APPROVED',         'Programare aprobata'
        APPT_COMPLETED        = 'APPT_COMPLETED',        'Consultatie finalizata'
        APPT_DELETED          = 'APPT_DELETED',          'Programare stearsa'
        APPT_NO_SHOW          = 'APPT_NO_SHOW',          'Neprezentare marcata'
        PROFILE_UPDATED       = 'PROFILE_UPDATED',       'Profil actualizat'
        PRESCRIPTION_CREATED  = 'PRESCRIPTION_CREATED',  'Reteta creata'
        PASSWORD_CHANGED      = 'PASSWORD_CHANGED',      'Parola schimbata'
        PATIENT_RECORD_VIEWED = 'PATIENT_RECORD_VIEWED', 'Fisa pacient vizualizata'
        AVAILABILITY_CHANGED  = 'AVAILABILITY_CHANGED',  'Disponibilitate schimbata'
        RATING_GIVEN          = 'RATING_GIVEN',          'Evaluare acordata'
        GDPR_EXPORT           = 'GDPR_EXPORT',           'Export date GDPR'
        PAYMENT_CREATED       = 'PAYMENT_CREATED',       'Plata inregistrata'
        CNAS_GENERATED        = 'CNAS_GENERATED',        'Cod CNAS generat'
        WALLET_TOPUP          = 'WALLET_TOPUP',          'Wallet reincarcat'
        CASHBACK_CREDIT       = 'CASHBACK_CREDIT',       'Cashback 5% acordat'
        SOFT_BAN              = 'SOFT_BAN',              'Blocare temporara 10 min'
        HARD_BAN              = 'HARD_BAN',              'Blocare permanenta cont/IP'
        BAN_REVOKED           = 'BAN_REVOKED',           'Ban revocat de admin'
        TWO_FA_SENT           = 'TWO_FA_SENT',           'Cod 2FA trimis'
        TWO_FA_SUCCESS        = 'TWO_FA_SUCCESS',        'Autentificare 2FA reusita'
        TWO_FA_FAILED         = 'TWO_FA_FAILED',         'Cod 2FA gresit'

    user       = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action     = models.CharField(max_length=50, choices=Action.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    metadata   = models.JSONField(default=dict, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} - {self.action}'

    @classmethod
    def log(cls, request, action, metadata=None):
        user = request.user if request.user.is_authenticated else None
        cls.objects.create(
            user=user,
            action=action,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata=metadata or {}
        )


class LoginAttempt(models.Model):
    """
    Tracker pentru brute-force protection.
    Treapta 1 (Soft Ban): 5 încercări consecutive → blocat 10 minute.
    Treapta 2 (Hard Ban): 30 încercări în 24h → blocat permanent.
    """
    username        = models.CharField(max_length=150, blank=True, default='')
    ip_address      = models.GenericIPAddressField()
    timestamp       = models.DateTimeField(auto_now_add=True)
    is_soft_banned  = models.BooleanField(default=False)
    soft_ban_until  = models.DateTimeField(null=True, blank=True)
    is_hard_banned  = models.BooleanField(default=False)
    hard_ban_reason = models.CharField(max_length=200, blank=True, default='')
    revoked         = models.BooleanField(default=False)
    revoked_at      = models.DateTimeField(null=True, blank=True)
    revoked_by      = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bans_revoked'
    )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        status = 'HARD_BAN' if self.is_hard_banned else ('SOFT_BAN' if self.is_soft_banned else 'attempt')
        return f'[{status}] {self.username or "?"} @ {self.ip_address} — {self.timestamp:%Y-%m-%d %H:%M}'

    @classmethod
    def get_ip(cls, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '0.0.0.0')

    @classmethod
    def check_ban(cls, request, username=''):
        """
        Returnează (is_banned, message) pentru request-ul curent.
        Verifică soft ban activ și hard ban pentru username sau IP.
        """
        from django.utils import timezone
        ip  = cls.get_ip(request)
        now = timezone.now()

        # Hard ban IP
        if cls.objects.filter(ip_address=ip, is_hard_banned=True, revoked=False).exists():
            return True, 'Acest IP a fost blocat permanent din cauza activității suspecte. Contactați administratorul.'

        # Hard ban username
        if username and cls.objects.filter(username=username, is_hard_banned=True, revoked=False).exists():
            return True, f'Contul "{username}" a fost blocat permanent. Contactați administratorul.'

        # Soft ban IP
        soft = cls.objects.filter(ip_address=ip, is_soft_banned=True, revoked=False).order_by('-soft_ban_until').first()
        if soft and soft.soft_ban_until and soft.soft_ban_until > now:
            minutes_left = max(1, int((soft.soft_ban_until - now).total_seconds() / 60))
            return True, f'Prea multe încercări eșuate. Încearcă din nou în {minutes_left} minut(e).'

        return False, ''

    @classmethod
    def record_failure(cls, request, username=''):
        from django.utils import timezone
        ip  = cls.get_ip(request)
        now = timezone.now()

        cls.objects.create(ip_address=ip, username=username)

        count_24h = cls.objects.filter(
            ip_address=ip,
            is_soft_banned=False,
            is_hard_banned=False,
            revoked=False,
            timestamp__gte=now - timezone.timedelta(hours=24),
        ).count()
        if count_24h >= 30:
            cls.objects.create(
                ip_address=ip, username=username,
                is_hard_banned=True,
                hard_ban_reason=f'{count_24h} incercari esuate in 24h',
            )
            return False, True

        recent_count = cls.objects.filter(
            ip_address=ip,
            is_soft_banned=False,
            is_hard_banned=False,
            revoked=False,
            timestamp__gte=now - timezone.timedelta(hours=1),
        ).count()
        if recent_count >= 5:
            ban_until = now + timezone.timedelta(minutes=10)
            cls.objects.create(
                ip_address=ip, username=username,
                is_soft_banned=True,
                soft_ban_until=ban_until,
            )
            return True, False

        return False, False


class TwoFactorCode(models.Model):
    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='two_factor_codes')
    code       = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'2FA {self.user.username} — {self.code} ({"folosit" if self.used else "valid"})'

    def is_valid(self):
        from django.utils import timezone
        return not self.used and self.expires_at > timezone.now()

    @classmethod
    def generate(cls, user):
        import random
        from django.utils import timezone
        cls.objects.filter(user=user, used=False).update(used=True)
        code = str(random.randint(100000, 999999))
        return cls.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )