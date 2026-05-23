from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncMonth

from .forms import (
    ClinicLoginForm, RegisterForm, AppointmentForm,
    PatientUserForm, PatientProfileForm,
    PrescriptionForm, ClinicPasswordChangeForm,
)
from .models import (
    CustomUser, Appointment, AuditLog,
    PatientProfile, DoctorProfile, Prescription,
)


# ── Helpers ──────────────────────────────────────────────

def _profile_pct(profile, user):
    fields = [user.first_name, user.last_name, user.email,
              profile.phone, profile.cnp, profile.blood_type, profile.allergies]
    filled = sum(1 for f in fields if f and str(f).strip())
    return round((filled / len(fields)) * 100)


def _get_notifications(user):
    confirmed = Appointment.objects.filter(
        patient=user, is_confirmed=True, date_time__gte=timezone.now(),
    ).select_related('doctor').order_by('date_time')[:5]
    return confirmed, confirmed.count()


def _redirect_by_role(user):
    if user.is_staff or user.is_superuser:
        return redirect('admin_reports')
    if user.is_doctor:
        return redirect('doctor_dashboard')
    if user.is_patient:
        return redirect('patient_dashboard')
    return redirect('home')


# ── Pagini publice ────────────────────────────────────────

def home_view(request):
    return render(request, 'index.html')


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    if request.method == 'POST':
        form = ClinicLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            AuditLog.log(request, AuditLog.Action.LOGIN_SUCCESS, metadata={'username': user.username})
            return _redirect_by_role(user)
        else:
            AuditLog.log(request, AuditLog.Action.LOGIN_FAILED, metadata={'username': request.POST.get('username', '')})
    else:
        form = ClinicLoginForm()
    return render(request, 'login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            PatientProfile.objects.get_or_create(user=user)
            login(request, user)
            AuditLog.log(request, AuditLog.Action.REGISTER, metadata={'username': user.username})
            return redirect('patient_dashboard')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def logout_view(request):
    AuditLog.log(request, AuditLog.Action.LOGOUT)
    logout(request)
    return redirect('login')


# ── Pacient ───────────────────────────────────────────────

@login_required(login_url='login')
def patient_dashboard(request):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    profile, _ = PatientProfile.objects.get_or_create(user=request.user)
    now = timezone.now()

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appt = form.save(commit=False)
            appt.patient = request.user
            appt.save()
            AuditLog.log(request, AuditLog.Action.APPT_CREATED, metadata={'doctor': appt.doctor.username})
            messages.success(request, 'Programarea a fost creată cu succes!')
            return redirect('patient_dashboard')
    else:
        form = AppointmentForm()

    all_appts       = Appointment.objects.filter(patient=request.user).select_related('doctor')
    upcoming        = all_appts.filter(date_time__gte=now).order_by('date_time')
    past            = all_appts.filter(date_time__lt=now).order_by('-date_time')
    last_visit      = past.first()
    confirmed_count = all_appts.filter(is_confirmed=True).count()
    pending_count   = all_appts.filter(is_confirmed=False).count()
    profile_pct     = _profile_pct(profile, request.user)
    notif_list, notif_count = _get_notifications(request.user)

    # Rețete pentru pacient
    prescriptions = Prescription.objects.filter(
        patient=request.user
    ).select_related('doctor', 'appointment').order_by('-created_at')[:5]

    return render(request, 'patient_dashboard.html', {
        'form':            form,
        'appointments':    all_appts,
        'upcoming':        upcoming,
        'past':            past,
        'last_visit':      last_visit,
        'profile':         profile,
        'confirmed_count': confirmed_count,
        'pending_count':   pending_count,
        'profile_pct':     profile_pct,
        'notif_list':      notif_list,
        'notif_count':     notif_count,
        'prescriptions':   prescriptions,
    })


@login_required(login_url='login')
def cancel_appointment(request, appointment_id):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, patient=request.user, is_confirmed=False)
    AuditLog.log(request, AuditLog.Action.APPT_DELETED, metadata={'appointment_id': appointment_id, 'cancelled_by': 'patient'})
    appt.delete()
    messages.info(request, 'Programarea a fost anulată.')
    return redirect('patient_dashboard')


@login_required(login_url='login')
def profile_edit(request):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    profile, _ = PatientProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        user_form    = PatientUserForm(request.POST, instance=request.user)
        profile_form = PatientProfileForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            AuditLog.log(request, AuditLog.Action.PROFILE_UPDATED)
            messages.success(request, 'Profilul a fost actualizat!')
            return redirect('patient_dashboard')
    else:
        user_form    = PatientUserForm(instance=request.user)
        profile_form = PatientProfileForm(instance=profile)
    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'profile_edit.html', {
        'user_form': user_form, 'profile_form': profile_form,
        'profile': profile, 'notif_list': notif_list, 'notif_count': notif_count,
    })


@login_required(login_url='login')
def profile_security(request):
    """Schimbare parolă — accesibil oricărui utilizator autentificat."""
    if request.method == 'POST':
        form = ClinicPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # nu deloghez după schimbare
            AuditLog.log(request, AuditLog.Action.PASSWORD_CHANGED)
            messages.success(request, 'Parola a fost schimbată cu succes!')
            return redirect('patient_dashboard' if request.user.is_patient else 'doctor_dashboard')
    else:
        form = ClinicPasswordChangeForm(request.user)
    notif_list, notif_count = _get_notifications(request.user) if request.user.is_patient else ([], 0)
    return render(request, 'profile_security.html', {
        'form': form, 'notif_list': notif_list, 'notif_count': notif_count,
    })


@login_required(login_url='login')
def doctors_list(request):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')

    # Căutare după specialitate
    specialty_filter = request.GET.get('specialty', '').strip()
    doctors = CustomUser.objects.filter(is_doctor=True, is_active=True)

    doctor_data = []
    specialties = set()
    for doc in doctors:
        try:
            dp = doc.doctor_profile
            if dp.specialization:
                specialties.add(dp.specialization)
        except DoctorProfile.DoesNotExist:
            dp = None
        if specialty_filter and dp:
            if specialty_filter.lower() not in (dp.specialization or '').lower():
                continue
        doctor_data.append({'user': doc, 'profile': dp})

    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'doctors_list.html', {
        'doctor_data':      doctor_data,
        'specialties':      sorted(specialties),
        'specialty_filter': specialty_filter,
        'notif_list':       notif_list,
        'notif_count':      notif_count,
    })


# ── Medic ─────────────────────────────────────────────────

@login_required(login_url='login')
def doctor_dashboard(request):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appointments = Appointment.objects.filter(
        doctor=request.user
    ).select_related('patient')

    try:
        doctor_profile = request.user.doctor_profile
    except DoctorProfile.DoesNotExist:
        doctor_profile = None

    return render(request, 'doctor_dashboard.html', {
        'appointments':   appointments,
        'doctor_profile': doctor_profile,
    })


@login_required(login_url='login')
def toggle_availability(request):
    """Medicul comută disponibilitatea sa."""
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    profile, _ = DoctorProfile.objects.get_or_create(user=request.user)
    profile.is_available = not profile.is_available
    profile.save()
    AuditLog.log(request, AuditLog.Action.AVAILABILITY_CHANGED,
                 metadata={'is_available': profile.is_available})
    status = 'Disponibil' if profile.is_available else 'Indisponibil'
    messages.success(request, f'Statusul tău a fost schimbat la: {status}')
    return redirect('doctor_dashboard')


@login_required(login_url='login')
def approve_appointment(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    appt.is_confirmed = True
    appt.save()
    AuditLog.log(request, AuditLog.Action.APPT_APPROVED, metadata={'appointment_id': appointment_id})
    messages.success(request, 'Programarea a fost aprobată.')
    return redirect('doctor_dashboard')


@login_required(login_url='login')
def delete_appointment(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    AuditLog.log(request, AuditLog.Action.APPT_DELETED, metadata={'patient': appt.patient.username})
    appt.delete()
    messages.info(request, 'Programarea a fost ștearsă.')
    return redirect('doctor_dashboard')


@login_required(login_url='login')
def patient_history(request, patient_id):
    """Fișa unui pacient — accesibilă doar medicului care a avut programări cu el."""
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')

    patient = get_object_or_404(CustomUser, id=patient_id, is_patient=True)

    # Securitate: verifică că medicul a avut cel puțin o programare cu pacientul
    has_appt = Appointment.objects.filter(doctor=request.user, patient=patient).exists()
    if not has_appt:
        messages.error(request, 'Nu ai acces la fișa acestui pacient.')
        return redirect('doctor_dashboard')

    try:
        patient_profile = patient.patient_profile
    except PatientProfile.DoesNotExist:
        patient_profile = None

    appointments = Appointment.objects.filter(
        doctor=request.user, patient=patient
    ).order_by('-date_time')

    prescriptions = Prescription.objects.filter(
        doctor=request.user, patient=patient
    ).order_by('-created_at')

    AuditLog.log(request, AuditLog.Action.PATIENT_RECORD_VIEWED,
                 metadata={'patient_id': str(patient.id), 'patient_username': patient.username})

    return render(request, 'patient_history.html', {
        'patient':         patient,
        'patient_profile': patient_profile,
        'appointments':    appointments,
        'prescriptions':   prescriptions,
    })


@login_required(login_url='login')
def add_prescription(request, appointment_id):
    """Medicul adaugă rețetă după consultație."""
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')

    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)

    # Verifică dacă există deja rețetă
    existing = Prescription.objects.filter(appointment=appt).first()
    if existing:
        messages.info(request, 'Există deja o rețetă pentru această programare.')
        return redirect('doctor_dashboard')

    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.appointment = appt
            prescription.doctor      = request.user
            prescription.patient     = appt.patient
            prescription.save()
            AuditLog.log(request, AuditLog.Action.PRESCRIPTION_CREATED,
                         metadata={'appointment_id': appointment_id, 'patient': appt.patient.username})
            messages.success(request, 'Rețeta a fost salvată.')
            return redirect('doctor_dashboard')
    else:
        form = PrescriptionForm()

    return render(request, 'add_prescription.html', {'form': form, 'appointment': appt})


# ── Admin ─────────────────────────────────────────────────

@login_required(login_url='login')
def admin_reports(request):
    """Pagina de statistici — accesibilă doar adminilor."""
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('home')

    now = timezone.now()

    # Statistici generale
    total_patients     = CustomUser.objects.filter(is_patient=True).count()
    total_doctors      = CustomUser.objects.filter(is_doctor=True).count()
    total_appointments = Appointment.objects.count()
    confirmed_appts    = Appointment.objects.filter(is_confirmed=True).count()
    available_doctors  = DoctorProfile.objects.filter(is_available=True).count()
    new_patients_month = CustomUser.objects.filter(
        is_patient=True, date_joined__month=now.month, date_joined__year=now.year
    ).count()

    # Programări per lună (ultimele 6 luni) — pentru grafic
    monthly_data = (
        Appointment.objects
        .filter(date_time__gte=now - timezone.timedelta(days=180))
        .annotate(month=TruncMonth('date_time'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    monthly_labels = [item['month'].strftime('%b %Y') for item in monthly_data]
    monthly_counts = [item['count'] for item in monthly_data]

    # Ultimele 10 acțiuni din audit
    audit_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]

    # Top medici după număr de programări
    top_doctors = (
        CustomUser.objects
        .filter(is_doctor=True)
        .annotate(appt_count=Count('appointments_as_doctor'))
        .order_by('-appt_count')[:5]
    )

    return render(request, 'admin_reports.html', {
        'total_patients':     total_patients,
        'total_doctors':      total_doctors,
        'total_appointments': total_appointments,
        'confirmed_appts':    confirmed_appts,
        'available_doctors':  available_doctors,
        'new_patients_month': new_patients_month,
        'monthly_labels':     monthly_labels,
        'monthly_counts':     monthly_counts,
        'audit_logs':         audit_logs,
        'top_doctors':        top_doctors,
    })
