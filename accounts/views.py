from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .forms import ClinicLoginForm, RegisterForm, AppointmentForm, PatientUserForm, PatientProfileForm
from .models import CustomUser, Appointment, AuditLog, PatientProfile, DoctorProfile


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
            AuditLog.log(request, AuditLog.Action.LOGIN_SUCCESS,
                         metadata={'username': user.username})
            return _redirect_by_role(user)
        else:
            AuditLog.log(request, AuditLog.Action.LOGIN_FAILED,
                         metadata={'username': request.POST.get('username', '')})
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
            AuditLog.log(request, AuditLog.Action.REGISTER,
                         metadata={'username': user.username})
            return redirect('patient_dashboard')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def logout_view(request):
    AuditLog.log(request, AuditLog.Action.LOGOUT)
    logout(request)
    return redirect('login')


def _profile_pct(profile, user):
    fields = [
        user.first_name, user.last_name, user.email,
        profile.phone, profile.cnp,
        profile.blood_type, profile.allergies,
    ]
    filled = sum(1 for f in fields if f and str(f).strip())
    return round((filled / len(fields)) * 100)


def _get_notifications(user):
    confirmed = Appointment.objects.filter(
        patient=user,
        is_confirmed=True,
        date_time__gte=timezone.now(),
    ).select_related('doctor').order_by('date_time')[:5]
    return confirmed, confirmed.count()


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
            AuditLog.log(request, AuditLog.Action.APPT_CREATED,
                         metadata={'doctor': appt.doctor.username})
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
    })


@login_required(login_url='login')
def cancel_appointment(request, appointment_id):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    appt = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient=request.user,
        is_confirmed=False
    )
    AuditLog.log(request, AuditLog.Action.APPT_DELETED,
                 metadata={'appointment_id': appointment_id, 'cancelled_by': 'patient'})
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
        'user_form':    user_form,
        'profile_form': profile_form,
        'profile':      profile,
        'notif_list':   notif_list,
        'notif_count':  notif_count,
    })


@login_required(login_url='login')
def doctors_list(request):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    doctors = CustomUser.objects.filter(is_doctor=True, is_active=True)
    doctor_data = []
    for doc in doctors:
        try:
            dp = doc.doctor_profile
        except DoctorProfile.DoesNotExist:
            dp = None
        doctor_data.append({'user': doc, 'profile': dp})

    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'doctors_list.html', {
        'doctor_data': doctor_data,
        'notif_list':  notif_list,
        'notif_count': notif_count,
    })


@login_required(login_url='login')
def doctor_dashboard(request):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appointments = Appointment.objects.filter(
        doctor=request.user
    ).select_related('patient')
    return render(request, 'doctor_dashboard.html', {'appointments': appointments})


@login_required(login_url='login')
def approve_appointment(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    appt.is_confirmed = True
    appt.save()
    AuditLog.log(request, AuditLog.Action.APPT_APPROVED,
                 metadata={'appointment_id': appointment_id})
    messages.success(request, 'Programarea a fost aprobată.')
    return redirect('doctor_dashboard')


@login_required(login_url='login')
def delete_appointment(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    AuditLog.log(request, AuditLog.Action.APPT_DELETED,
                 metadata={'patient': appt.patient.username})
    appt.delete()
    messages.info(request, 'Programarea a fost ștearsă.')
    return redirect('doctor_dashboard')


def _redirect_by_role(user):
    if user.is_staff or user.is_superuser:
        return redirect('/admin/')
    if user.is_doctor:
        return redirect('doctor_dashboard')
    if user.is_patient:
        return redirect('patient_dashboard')
    return redirect('home')
