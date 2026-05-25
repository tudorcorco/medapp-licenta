from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


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
    user       = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='patient_profile')
    cnp        = models.CharField(max_length=13, blank=True, default='')
    birth_date = models.DateField(null=True, blank=True)
    blood_type = models.CharField(max_length=5, blank=True, default='')
    allergies  = models.TextField(blank=True, default='')
    phone      = models.CharField(max_length=20, blank=True, default='')

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


class Appointment(models.Model):
    patient      = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='appointments_as_patient')
    doctor       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='appointments_as_doctor')
    date_time    = models.DateTimeField()
    reason       = models.TextField(blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_time']

    def __str__(self):
        return f'{self.patient.username} -> Dr. {self.doctor.username} ({self.date_time.strftime("%Y-%m-%d %H:%M")})'


class Prescription(models.Model):
    appointment  = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='prescription')
    doctor       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='prescriptions_written')
    patient      = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='prescriptions_received')
    diagnosis    = models.TextField(blank=True, default='')
    medication   = models.TextField()
    instructions = models.TextField(blank=True, default='')
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Rețetă: {self.patient.username} de la Dr. {self.doctor.username}'


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


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN_SUCCESS        = 'LOGIN_SUCCESS',        'Autentificare reușită'
        LOGIN_FAILED         = 'LOGIN_FAILED',         'Autentificare eșuată'
        LOGOUT               = 'LOGOUT',               'Deconectare'
        REGISTER             = 'REGISTER',             'Înregistrare cont nou'
        APPT_CREATED         = 'APPT_CREATED',         'Programare creată'
        APPT_APPROVED        = 'APPT_APPROVED',        'Programare aprobată'
        APPT_COMPLETED       = 'APPT_COMPLETED',       'Consultație finalizată'
        APPT_DELETED         = 'APPT_DELETED',         'Programare ștearsă'
        PROFILE_UPDATED      = 'PROFILE_UPDATED',      'Profil actualizat'
        PRESCRIPTION_CREATED = 'PRESCRIPTION_CREATED', 'Rețetă creată'
        PASSWORD_CHANGED     = 'PASSWORD_CHANGED',     'Parolă schimbată'
        PATIENT_RECORD_VIEWED= 'PATIENT_RECORD_VIEWED','Fișă pacient vizualizată'
        AVAILABILITY_CHANGED = 'AVAILABILITY_CHANGED', 'Disponibilitate schimbată'
        RATING_GIVEN         = 'RATING_GIVEN',         'Evaluare acordată'
        GDPR_EXPORT          = 'GDPR_EXPORT',          'Export date GDPR'

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
