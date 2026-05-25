from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Avg
from django.db.models.functions import TruncMonth
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
import json

from .forms import (
    ClinicLoginForm, RegisterForm, AppointmentForm,
    PatientUserForm, PatientProfileForm,
    PrescriptionForm, ClinicPasswordChangeForm,
)
from .models import (
    CustomUser, Appointment, AuditLog,
    PatientProfile, DoctorProfile, Prescription, Rating,
)


def _profile_pct(profile, user):
    fields = [user.first_name, user.last_name, user.email,
              profile.phone, profile.cnp, profile.blood_type, profile.allergies]
    filled = sum(1 for f in fields if f and str(f).strip())
    return round((filled / len(fields)) * 100)


def _get_notifications(user):
    confirmed = Appointment.objects.filter(
        patient=user, is_confirmed=True,
        is_completed=False, date_time__gte=timezone.now(),
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


def _send_email_safe(subject, message, recipient):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        pass


def _get_admin_stats(now):
    total_patients     = CustomUser.objects.filter(is_patient=True).count()
    total_doctors      = CustomUser.objects.filter(is_doctor=True).count()
    total_appointments = Appointment.objects.count()
    confirmed_appts    = Appointment.objects.filter(is_confirmed=True).count()
    completed_appts    = Appointment.objects.filter(is_completed=True).count()
    available_doctors  = DoctorProfile.objects.filter(is_available=True).count()
    new_patients_month = CustomUser.objects.filter(
        is_patient=True, date_joined__month=now.month, date_joined__year=now.year
    ).count()

    revenue_total = 0
    revenue_month = 0
    for dp in DoctorProfile.objects.all():
        completed_all   = Appointment.objects.filter(
            doctor=dp.user, is_completed=True
        ).count()
        completed_month = Appointment.objects.filter(
            doctor=dp.user, is_completed=True,
            date_time__month=now.month, date_time__year=now.year
        ).count()
        revenue_total += completed_all   * float(dp.consultation_fee)
        revenue_month += completed_month * float(dp.consultation_fee)

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

    status_counts = [
        Appointment.objects.filter(is_completed=True).count(),
        Appointment.objects.filter(is_confirmed=True, is_completed=False).count(),
        Appointment.objects.filter(is_confirmed=False, is_completed=False).count(),
    ]

    top_doctors_raw = CustomUser.objects.filter(is_doctor=True).annotate(
        appt_count=Count('appointments_as_doctor')
    ).order_by('-appt_count')[:5]

    top_doctors = []
    for doc in top_doctors_raw:
        try:
            fee  = float(doc.doctor_profile.consultation_fee)
            spec = doc.doctor_profile.specialization
        except DoctorProfile.DoesNotExist:
            fee  = 0
            spec = ''
        completed = Appointment.objects.filter(doctor=doc, is_completed=True).count()
        top_doctors.append({
            'user': doc,
            'specialization': spec,
            'appt_count': doc.appt_count,
            'revenue': completed * fee,
        })

    def _monthly_revenue(months_back):
        labels, data = [], []
        for i in range(months_back - 1, -1, -1):
            d = now - timezone.timedelta(days=i * 30)
            rev = 0
            for dp in DoctorProfile.objects.all():
                c = Appointment.objects.filter(
                    doctor=dp.user, is_completed=True,
                    date_time__month=d.month, date_time__year=d.year
                ).count()
                rev += c * float(dp.consultation_fee)
            labels.append(d.strftime('%b %Y'))
            data.append(int(rev))
        return labels, data

    def _monthly_patients(months_back):
        labels, data = [], []
        for i in range(months_back - 1, -1, -1):
            d = now - timezone.timedelta(days=i * 30)
            count = CustomUser.objects.filter(
                is_patient=True,
                date_joined__month=d.month,
                date_joined__year=d.year
            ).count()
            labels.append(d.strftime('%b %Y'))
            data.append(count)
        return labels, data

    revenue_labels,     revenue_data     = _monthly_revenue(6)
    revenue_labels_1y,  revenue_data_1y  = _monthly_revenue(12)
    patients_labels,    patients_data    = _monthly_patients(6)
    patients_labels_1y, patients_data_1y = _monthly_patients(12)

    return {
        'total_patients':      total_patients,
        'total_doctors':       total_doctors,
        'total_appointments':  total_appointments,
        'confirmed_appts':     confirmed_appts,
        'completed_appts':     completed_appts,
        'available_doctors':   available_doctors,
        'new_patients_month':  new_patients_month,
        'revenue_total':       int(revenue_total),
        'revenue_month':       int(revenue_month),
        'monthly_labels':      monthly_labels,
        'monthly_counts':      monthly_counts,
        'status_counts':       status_counts,
        'top_doctors':         top_doctors,
        'revenue_labels':      revenue_labels,
        'revenue_data':        revenue_data,
        'revenue_labels_1y':   revenue_labels_1y,
        'revenue_data_1y':     revenue_data_1y,
        'patients_labels':     patients_labels,
        'patients_data':       patients_data,
        'patients_labels_1y':  patients_labels_1y,
        'patients_data_1y':    patients_data_1y,
    }


def home_view(request):
    from django.utils import timezone
    today = timezone.now().date()
    medici_activi      = DoctorProfile.objects.filter(is_available=True).count()
    consultatii_totale = Appointment.objects.filter(is_completed=True).count()
    programari_azi     = Appointment.objects.filter(date_time__date=today).count()
    return render(request, 'index.html', {
        'medici_activi':      medici_activi,
        'consultatii_totale': consultatii_totale,
        'programari_azi':     programari_azi,
    })


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


@login_required(login_url='login')
def patient_dashboard(request):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    profile, _ = PatientProfile.objects.get_or_create(user=request.user)
    now = timezone.now()

    all_appts       = Appointment.objects.filter(patient=request.user).select_related('doctor')
    upcoming        = all_appts.filter(date_time__gte=now, is_completed=False).order_by('date_time')
    past            = (all_appts.filter(date_time__lt=now) | all_appts.filter(is_completed=True)).distinct().order_by('-date_time')
    last_visit      = all_appts.filter(is_completed=True).order_by('-date_time').first()
    next_appt       = upcoming.first()
    confirmed_count = all_appts.filter(is_confirmed=True).count()
    pending_count   = all_appts.filter(is_confirmed=False, is_completed=False).count()
    completed_count = all_appts.filter(is_completed=True).count()
    profile_pct     = _profile_pct(profile, request.user)
    prescriptions   = Prescription.objects.filter(patient=request.user).select_related('doctor').order_by('-created_at')[:5]
    notif_list, notif_count = _get_notifications(request.user)

    unrated = all_appts.filter(
        is_completed=True
    ).exclude(rating__isnull=False).order_by('-date_time').first()

    hour = now.hour
    greeting = 'Bună dimineața' if hour < 12 else ('Bună ziua' if hour < 18 else 'Bună seara')

    return render(request, 'patient_dashboard.html', {
        'appointments': all_appts, 'upcoming': upcoming, 'past': past,
        'last_visit': last_visit, 'next_appt': next_appt, 'profile': profile,
        'confirmed_count': confirmed_count, 'pending_count': pending_count,
        'completed_count': completed_count, 'profile_pct': profile_pct,
        'notif_list': notif_list, 'notif_count': notif_count,
        'prescriptions': prescriptions, 'greeting': greeting,
        'unrated': unrated,
    })


@login_required(login_url='login')
def cancel_appointment(request, appointment_id):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, patient=request.user, is_confirmed=False)
    AuditLog.log(request, AuditLog.Action.APPT_DELETED, metadata={'appointment_id': appointment_id})
    appt.delete()
    messages.info(request, 'Programarea a fost anulată.')
    return redirect('patient_dashboard')


@login_required(login_url='login')
def rate_doctor(request, appointment_id):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, patient=request.user, is_completed=True)

    if Rating.objects.filter(appointment=appt).exists():
        messages.info(request, 'Ai evaluat deja această consultație.')
        return redirect('patient_dashboard')

    if request.method == 'POST':
        score   = request.POST.get('score')
        comment = request.POST.get('comment', '').strip()
        if score and score.isdigit() and 1 <= int(score) <= 5:
            Rating.objects.create(
                appointment=appt,
                patient=request.user,
                doctor=appt.doctor,
                score=int(score),
                comment=comment,
            )
            AuditLog.log(request, AuditLog.Action.RATING_GIVEN,
                         metadata={'doctor': appt.doctor.username, 'score': score})
            messages.success(request, 'Mulțumim pentru evaluare!')
            return redirect('patient_dashboard')
        else:
            messages.error(request, 'Te rugăm să selectezi un număr de stele.')

    return render(request, 'rate_doctor.html', {'appointment': appt})


@login_required(login_url='login')
def gdpr_export(request):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    import io

    user    = request.user
    profile = getattr(user, 'patient_profile', None)
    appts   = Appointment.objects.filter(patient=user).select_related('doctor')
    prescriptions = Prescription.objects.filter(patient=user).select_related('doctor')

    def clean(text):
        if not text:
            return '—'
        return (str(text)
            .replace('ă', 'a').replace('Ă', 'A')
            .replace('â', 'a').replace('Â', 'A')
            .replace('î', 'i').replace('Î', 'I')
            .replace('ș', 's').replace('Ș', 'S')
            .replace('ț', 't').replace('Ț', 'T')
            .replace('ş', 's').replace('Ş', 'S')
            .replace('ţ', 't').replace('Ţ', 'T')
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Title'], fontSize=20, spaceAfter=6)
    h2_style    = ParagraphStyle('h2', parent=styles['Heading2'], fontSize=13,
                                 spaceBefore=16, spaceAfter=6,
                                 textColor=colors.HexColor('#1B5FAD'))
    normal = styles['Normal']
    normal.fontSize = 10

    def make_table(data, col_widths):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#EBF4FF')),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#F7FAFC')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    def make_header_table(data, col_widths):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B5FAD')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7FAFC')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    story = []

    story.append(Paragraph('Export Date Personale - MedApp', title_style))
    story.append(Paragraph(f'Generat la: {timezone.now().strftime("%d %B %Y, %H:%M")}', normal))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph('Date cont', h2_style))
    story.append(make_table([
        ['Username',          clean(user.username)],
        ['Nume complet',      clean(user.get_full_name() or '—')],
        ['Email',             clean(user.email)],
        ['Data inregistrarii', clean(user.date_joined.strftime('%d %B %Y'))],
    ], [5*cm, 12*cm]))

    story.append(Paragraph('Date medicale', h2_style))
    story.append(make_table([
        ['CNP',          clean(profile.cnp if profile else '—')],
        ['Data nasterii', clean(str(profile.birth_date) if profile and profile.birth_date else '—')],
        ['Grup sanguin', clean(profile.blood_type if profile else '—')],
        ['Alergii',      clean(profile.allergies if profile else '—')],
        ['Telefon',      clean(profile.phone if profile else '—')],
    ], [5*cm, 12*cm]))

    story.append(Paragraph('Programari', h2_style))
    if appts.exists():
        data = [['Medic', 'Data', 'Status']]
        for a in appts:
            status = 'Finalizata' if a.is_completed else ('Confirmata' if a.is_confirmed else 'In asteptare')
            data.append([
                clean(f'Dr. {a.doctor.get_full_name() or a.doctor.username}'),
                a.date_time.strftime('%d %B %Y, %H:%M'),
                status,
            ])
        story.append(make_header_table(data, [7*cm, 6*cm, 4*cm]))
    else:
        story.append(Paragraph('Nicio programare inregistrata.', normal))

    story.append(Paragraph('Retete', h2_style))
    if prescriptions.exists():
        data = [['Medic', 'Data', 'Diagnostic']]
        for r in prescriptions:
            data.append([
                clean(f'Dr. {r.doctor.get_full_name() or r.doctor.username}'),
                r.created_at.strftime('%d %B %Y'),
                clean(r.diagnosis or '—'),
            ])
        story.append(make_header_table(data, [7*cm, 4*cm, 6*cm]))
    else:
        story.append(Paragraph('Nicio reteta inregistrata.', normal))

    doc.build(story)
    buffer.seek(0)

    AuditLog.log(request, AuditLog.Action.GDPR_EXPORT)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="datele_mele_medapp_{timezone.now().strftime("%Y%m%d")}.pdf"'
    return response


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
    if request.method == 'POST':
        form = ClinicPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
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
        'doctor_data': doctor_data, 'specialties': sorted(specialties),
        'specialty_filter': specialty_filter,
        'notif_list': notif_list, 'notif_count': notif_count,
    })


@login_required(login_url='login')
def doctor_profile(request, doctor_id):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    doctor = get_object_or_404(CustomUser, id=doctor_id, is_doctor=True)
    try:
        profile = doctor.doctor_profile
    except DoctorProfile.DoesNotExist:
        profile = None

    total_appointments     = Appointment.objects.filter(doctor=doctor).count()
    confirmed_appointments = Appointment.objects.filter(doctor=doctor, is_confirmed=True).count()
    unique_patients        = Appointment.objects.filter(doctor=doctor).values('patient').distinct().count()
    avg_rating             = profile.average_rating() if profile else None
    rating_count           = profile.rating_count() if profile else 0
    recent_ratings         = Rating.objects.filter(doctor=doctor).select_related('patient').order_by('-created_at')[:5]

    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'doctor_profile.html', {
        'doctor': doctor, 'profile': profile,
        'total_appointments': total_appointments,
        'confirmed_appointments': confirmed_appointments,
        'unique_patients': unique_patients,
        'avg_rating': avg_rating, 'rating_count': rating_count,
        'recent_ratings': recent_ratings,
        'notif_list': notif_list, 'notif_count': notif_count,
    })


@login_required(login_url='login')
def new_appointment(request, doctor_id):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    doctor = get_object_or_404(CustomUser, id=doctor_id, is_doctor=True)
    try:
        doctor_profile_obj = doctor.doctor_profile
        if not doctor_profile_obj.is_available:
            messages.error(request, 'Acest medic nu este disponibil momentan.')
            return redirect('doctor_profile', doctor_id=doctor_id)
    except DoctorProfile.DoesNotExist:
        doctor_profile_obj = None
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appt         = form.save(commit=False)
            appt.patient = request.user
            appt.doctor  = doctor
            appt.save()
            AuditLog.log(request, AuditLog.Action.APPT_CREATED, metadata={'doctor': doctor.username})
            messages.success(request, 'Programarea a fost creată cu succes!')
            return redirect('patient_dashboard')
    else:
        form = AppointmentForm()
    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'new_appointment.html', {
        'form': form, 'selected_doctor': doctor,
        'notif_list': notif_list, 'notif_count': notif_count,
    })


@login_required(login_url='login')
def doctor_dashboard(request):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appointments = Appointment.objects.filter(doctor=request.user).select_related('patient')
    try:
        doctor_profile_obj = request.user.doctor_profile
    except DoctorProfile.DoesNotExist:
        doctor_profile_obj = None
    return render(request, 'doctor_dashboard.html', {
        'appointments': appointments, 'doctor_profile': doctor_profile_obj,
    })


@login_required(login_url='login')
def doctor_profile_edit(request):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    profile, _ = DoctorProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name  = request.POST.get('last_name', '').strip()
        request.user.email      = request.POST.get('email', '').strip()
        request.user.save()
        profile.specialization   = request.POST.get('specialization', '').strip()
        profile.consultation_fee = request.POST.get('consultation_fee', 0)
        profile.license_number   = request.POST.get('license_number', '').strip()
        profile.bio              = request.POST.get('bio', '').strip()
        profile.is_available     = 'is_available' in request.POST
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']
        profile.save()
        AuditLog.log(request, AuditLog.Action.PROFILE_UPDATED)
        messages.success(request, 'Profilul a fost actualizat!')
        return redirect('doctor_dashboard')
    return render(request, 'doctor_profile_edit.html', {'profile': profile})


@login_required(login_url='login')
def toggle_availability(request):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    profile, _ = DoctorProfile.objects.get_or_create(user=request.user)
    profile.is_available = not profile.is_available
    profile.save()
    AuditLog.log(request, AuditLog.Action.AVAILABILITY_CHANGED, metadata={'is_available': profile.is_available})
    messages.success(request, f'Status schimbat la: {"Disponibil" if profile.is_available else "Indisponibil"}')
    return redirect('doctor_dashboard')


@login_required(login_url='login')
def approve_appointment(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    appt.is_confirmed = True
    appt.save()
    AuditLog.log(request, AuditLog.Action.APPT_APPROVED, metadata={'appointment_id': appointment_id})

    _send_email_safe(
        subject='Programarea ta a fost confirmată — MedApp',
        message=f'Bună {appt.patient.get_full_name() or appt.patient.username},\n\n'
                f'Programarea ta la Dr. {appt.doctor.get_full_name() or appt.doctor.username} '
                f'din data de {appt.date_time.strftime("%d %B %Y, ora %H:%M")} a fost confirmată.\n\n'
                f'Te așteptăm!\nEchipa MedApp',
        recipient=appt.patient.email,
    )

    messages.success(request, 'Programarea a fost aprobată.')
    return redirect('doctor_dashboard')


@login_required(login_url='login')
def complete_appointment(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    appt.is_completed = True
    appt.is_confirmed = True
    appt.save()
    AuditLog.log(request, AuditLog.Action.APPT_COMPLETED, metadata={'appointment_id': appointment_id})
    messages.success(request, 'Consultația a fost marcată ca finalizată.')
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
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    patient = get_object_or_404(CustomUser, id=patient_id, is_patient=True)
    if not Appointment.objects.filter(doctor=request.user, patient=patient).exists():
        messages.error(request, 'Nu ai acces la fișa acestui pacient.')
        return redirect('doctor_dashboard')
    try:
        patient_profile = patient.patient_profile
    except PatientProfile.DoesNotExist:
        patient_profile = None
    appointments  = Appointment.objects.filter(doctor=request.user, patient=patient).order_by('-date_time')
    prescriptions = Prescription.objects.filter(doctor=request.user, patient=patient).order_by('-created_at')
    AuditLog.log(request, AuditLog.Action.PATIENT_RECORD_VIEWED, metadata={'patient_username': patient.username})
    return render(request, 'patient_history.html', {
        'patient': patient, 'patient_profile': patient_profile,
        'appointments': appointments, 'prescriptions': prescriptions,
    })


@login_required(login_url='login')
def add_prescription(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    if Prescription.objects.filter(appointment=appt).exists():
        messages.info(request, 'Există deja o rețetă pentru această programare.')
        return redirect('doctor_dashboard')
    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            rx             = form.save(commit=False)
            rx.appointment = appt
            rx.doctor      = request.user
            rx.patient     = appt.patient
            rx.save()
            AuditLog.log(request, AuditLog.Action.PRESCRIPTION_CREATED, metadata={'patient': appt.patient.username})
            messages.success(request, 'Rețeta a fost salvată.')
            return redirect('doctor_dashboard')
    else:
        form = PrescriptionForm()
    return render(request, 'add_prescription.html', {'form': form, 'appointment': appt})


@login_required(login_url='login')
def admin_reports(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('home')
    now = timezone.now()
    ctx = _get_admin_stats(now)
    ctx['recent_appointments'] = Appointment.objects.select_related('patient', 'doctor').order_by('-created_at')[:8]
    ctx['audit_logs']          = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]
    return render(request, 'admin_dashboard.html', ctx)


@login_required(login_url='login')
def admin_stats(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('home')
    now = timezone.now()
    ctx = _get_admin_stats(now)
    return render(request, 'admin_stats.html', ctx)


@login_required(login_url='login')
def admin_profile_edit(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('home')
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name  = request.POST.get('last_name', '').strip()
        request.user.email      = request.POST.get('email', '').strip()
        request.user.save()
        AuditLog.log(request, AuditLog.Action.PROFILE_UPDATED)
        messages.success(request, 'Profilul a fost actualizat!')
        return redirect('admin_reports')
    return render(request, 'admin_profile_edit.html', {'user': request.user})
