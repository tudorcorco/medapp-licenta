from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from django.db.models.functions import TruncMonth
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
import json
import uuid

from .forms import (
    ClinicLoginForm, RegisterForm, AppointmentForm,
    PatientUserForm, PatientProfileForm,
    PrescriptionForm, ClinicPasswordChangeForm, PaymentForm,
)
from .models import (
    CustomUser, Appointment, AuditLog,
    PatientProfile, DoctorProfile, Prescription, Rating,
    Payment, Wallet,
)


# ── HELPERS ────────────────────────────────────────────────────────────────────

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
            fail_silently=False,
        )
    except Exception as e:
        print(f"EMAIL ERROR: {e}")


def _get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


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
        completed_all   = Appointment.objects.filter(doctor=dp.user, is_completed=True).count()
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
            score = doc.doctor_profile.performance_score()
        except DoctorProfile.DoesNotExist:
            fee  = 0
            spec = ''
            score = 0
        completed = Appointment.objects.filter(doctor=doc, is_completed=True).count()
        top_doctors.append({
            'user': doc,
            'specialization': spec,
            'appt_count': doc.appt_count,
            'revenue': completed * fee,
            'performance_score': score,
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


# ── PUBLIC ─────────────────────────────────────────────────────────────────────

def home_view(request):
    today              = timezone.localdate()
    medici             = DoctorProfile.objects.select_related('user').all()
    medici_activi      = DoctorProfile.objects.filter(is_available=True).count()
    consultatii_totale = Appointment.objects.filter(is_completed=True).count()
    programari_azi     = Appointment.objects.filter(created_at__date=today).count()
    return render(request, 'index.html', {
        'medici':             medici,
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
            _get_or_create_wallet(user)
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


# ── PACIENT ────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def patient_dashboard(request):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    profile, _ = PatientProfile.objects.get_or_create(user=request.user)
    wallet     = _get_or_create_wallet(request.user)
    now        = timezone.now()

    all_appts       = Appointment.objects.filter(patient=request.user).select_related('doctor')
    upcoming        = all_appts.filter(date_time__gte=now, is_completed=False, is_no_show=False).order_by('date_time')
    past            = (all_appts.filter(date_time__lt=now) | all_appts.filter(is_completed=True)).distinct().order_by('-date_time')
    last_visit      = all_appts.filter(is_completed=True).order_by('-date_time').first()
    next_appt       = upcoming.first()
    confirmed_count = all_appts.filter(is_confirmed=True).count()
    pending_count   = all_appts.filter(is_confirmed=False, is_completed=False, is_no_show=False).count()
    completed_count = all_appts.filter(is_completed=True).count()
    no_show_count   = all_appts.filter(is_no_show=True).count()
    profile_pct     = _profile_pct(profile, request.user)
    prescriptions   = Prescription.objects.filter(patient=request.user).select_related('doctor').order_by('-created_at')[:5]
    notif_list, notif_count = _get_notifications(request.user)
    payments        = Payment.objects.filter(payer=request.user).order_by('-created_at')[:5]

    unrated = all_appts.filter(
        is_completed=True
    ).exclude(rating__isnull=False).order_by('-date_time').first()

    hour = now.hour
    greeting = 'Bună dimineața' if hour < 12 else ('Bună ziua' if hour < 18 else 'Bună seara')

    return render(request, 'patient_dashboard.html', {
        'appointments': all_appts, 'upcoming': upcoming, 'past': past,
        'last_visit': last_visit, 'next_appt': next_appt, 'profile': profile,
        'confirmed_count': confirmed_count, 'pending_count': pending_count,
        'completed_count': completed_count, 'no_show_count': no_show_count,
        'profile_pct': profile_pct,
        'notif_list': notif_list, 'notif_count': notif_count,
        'prescriptions': prescriptions, 'greeting': greeting,
        'unrated': unrated, 'wallet': wallet, 'payments': payments,
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
def payment_view(request, appointment_id):
    """Pagina de plată pentru o programare"""
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    appt   = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
    wallet = _get_or_create_wallet(request.user)

    try:
        dp  = appt.doctor.doctor_profile
        fee = float(dp.consultation_fee)
    except DoctorProfile.DoesNotExist:
        fee = 0

    # Daca e decontat CNAS, costul e 0
    if appt.cnas_covered:
        fee = 0

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            method         = form.cleaned_data['method']
            note           = form.cleaned_data['note']
            pay_for        = form.cleaned_data.get('pay_for_patient')
            beneficiary    = pay_for if pay_for else request.user
            amount         = fee

            if method == Payment.Method.WALLET:
                if wallet.balance < amount:
                    messages.error(request, f'Sold insuficient în wallet. Ai {wallet.balance} RON, necesari {amount} RON.')
                    return redirect('payment_view', appointment_id=appointment_id)
                wallet.balance -= amount
                wallet.save()

            if method == Payment.Method.ONLINE:
                # Simulare Stripe — in productie aici ai stripe.PaymentIntent.create()
                stripe_sim_id = f'pi_sim_{uuid.uuid4().hex[:16]}'
                payment = Payment.objects.create(
                    appointment=appt,
                    payer=request.user,
                    beneficiary=beneficiary,
                    amount=amount,
                    method=method,
                    status=Payment.Status.COMPLETED,
                    stripe_id=stripe_sim_id,
                    note=note,
                )
                messages.success(request, f'Plată online simulată cu succes! Ref: {payment.reference}')
            else:
                payment = Payment.objects.create(
                    appointment=appt,
                    payer=request.user,
                    beneficiary=beneficiary,
                    amount=amount,
                    method=method,
                    status=Payment.Status.COMPLETED,
                    note=note,
                )
                messages.success(request, f'Plată înregistrată! Ref: {payment.reference}')

            appt.payment_method = method
            appt.amount_paid    = amount
            appt.save()

            AuditLog.log(request, AuditLog.Action.PAYMENT_CREATED,
                         metadata={'appointment_id': appt.id, 'method': method, 'amount': str(amount)})

            return redirect('patient_dashboard')
    else:
        form = PaymentForm()

    return render(request, 'payment.html', {
        'form': form, 'appointment': appt, 'fee': fee, 'wallet': wallet,
    })


@login_required(login_url='login')
def wallet_topup(request):
    """Reîncărcare wallet cu sumă simulată"""
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    wallet = _get_or_create_wallet(request.user)
    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0')
        try:
            amount = float(amount_str)
            if 1 <= amount <= 5000:
                wallet.balance += amount
                wallet.save()
                AuditLog.log(request, AuditLog.Action.WALLET_TOPUP, metadata={'amount': amount})
                messages.success(request, f'{amount} RON adăugați în wallet!')
            else:
                messages.error(request, 'Suma trebuie să fie între 1 și 5000 RON.')
        except ValueError:
            messages.error(request, 'Sumă invalidă.')
    return redirect('patient_dashboard')


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

    styles     = getSampleStyleSheet()
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
        ['Username',           clean(user.username)],
        ['Nume complet',       clean(user.get_full_name() or '—')],
        ['Email',              clean(user.email)],
        ['Data inregistrarii', clean(user.date_joined.strftime('%d %B %Y'))],
    ], [5*cm, 12*cm]))

    story.append(Paragraph('Date medicale', h2_style))
    story.append(make_table([
        ['CNP',            clean(profile.cnp if profile else '—')],
        ['Data nasterii',  clean(str(profile.birth_date) if profile and profile.birth_date else '—')],
        ['Grup sanguin',   clean(profile.blood_type if profile else '—')],
        ['Alergii',        clean(profile.allergies if profile else '—')],
        ['Telefon',        clean(profile.phone if profile else '—')],
        ['Asigurat CNAS',  'Da' if (profile and profile.is_insured) else 'Nu'],
        ['Card sanatate',  clean(profile.health_card_serial if profile else '—')],
    ], [5*cm, 12*cm]))

    story.append(Paragraph('Programari', h2_style))
    if appts.exists():
        data = [['Medic', 'Data', 'Status', 'Plata']]
        for a in appts:
            if a.is_no_show:
                status = 'Neprezentare'
            elif a.is_completed:
                status = 'Finalizata'
            elif a.is_confirmed:
                status = 'Confirmata'
            else:
                status = 'In asteptare'
            data.append([
                clean(f'Dr. {a.doctor.get_full_name() or a.doctor.username}'),
                a.date_time.strftime('%d %B %Y, %H:%M'),
                status,
                clean(a.payment_method or '—'),
            ])
        story.append(make_header_table(data, [6*cm, 5*cm, 3*cm, 3*cm]))
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
    sort_by          = request.GET.get('sort', 'rating')
    doctors          = CustomUser.objects.filter(is_doctor=True, is_active=True)
    doctor_data      = []
    specialties      = set()

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

    if sort_by == 'performance':
        doctor_data.sort(key=lambda x: x['profile'].performance_score() if x['profile'] else 0, reverse=True)
    else:
        doctor_data.sort(key=lambda x: x['profile'].average_rating() or 0 if x['profile'] else 0, reverse=True)

    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'doctors_list.html', {
        'doctor_data': doctor_data, 'specialties': sorted(specialties),
        'specialty_filter': specialty_filter, 'sort_by': sort_by,
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
    performance_score      = profile.performance_score() if profile else 0
    recent_ratings         = Rating.objects.filter(doctor=doctor).select_related('patient').order_by('-created_at')[:5]

    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'doctor_profile.html', {
        'doctor': doctor, 'profile': profile,
        'total_appointments': total_appointments,
        'confirmed_appointments': confirmed_appointments,
        'unique_patients': unique_patients,
        'avg_rating': avg_rating, 'rating_count': rating_count,
        'performance_score': performance_score,
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

    try:
        patient_profile = request.user.patient_profile
    except PatientProfile.DoesNotExist:
        patient_profile = None

    if request.method == 'POST':
        print(">>> PAYMENT METHOD PRIMIT:", request.POST.get('payment_method'))
        print(">>> TOT POST-UL:", dict(request.POST))
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appt                 = form.save(commit=False)
            appt.patient         = request.user
            appt.doctor          = doctor
            appt.referral_serial = form.cleaned_data.get('referral_serial', '')
            appt.payment_method  = request.POST.get('payment_method', 'CASH')
            appt.save()
            AuditLog.log(request, AuditLog.Action.APPT_CREATED, metadata={'doctor': doctor.username})
            messages.success(request, 'Programarea a fost creată cu succes!')
            if appt.payment_method == 'CARD_ONLINE':
                return redirect('card_checkout', appointment_id=appt.id)
            return redirect('patient_dashboard')
    else:
        form = AppointmentForm()

    notif_list, notif_count = _get_notifications(request.user)
    return render(request, 'new_appointment.html', {
        'form': form,
        'selected_doctor': doctor,
        'patient_profile': patient_profile,
        'notif_list': notif_list,
        'notif_count': notif_count,
    })

@login_required(login_url='login')
def card_checkout(request, appointment_id):
    if not getattr(request.user, 'is_patient', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
 
    try:
        fee = float(appt.doctor.doctor_profile.consultation_fee)
    except DoctorProfile.DoesNotExist:
        fee = 0
 
    if request.method == 'POST' and request.POST.get('confirmed') == '1':
        stripe_ref = request.POST.get('stripe_ref', '')
        Payment.objects.create(
            appointment=appt,
            payer=request.user,
            beneficiary=request.user,
            amount=fee,
            method=Payment.Method.ONLINE,
            status=Payment.Status.COMPLETED,
            stripe_id=stripe_ref,
        )
        appt.payment_method = 'CARD_ONLINE'
        appt.amount_paid    = fee
        appt.save()
        AuditLog.log(request, AuditLog.Action.PAYMENT_CREATED,
                     metadata={'method': 'CARD_ONLINE', 'amount': fee, 'ref': stripe_ref})
        messages.success(request, f'Plată online confirmată! Ref: {stripe_ref}')
        return redirect('patient_dashboard')
 
    return render(request, 'card_checkout.html', {
        'appointment': appt,
        'fee': fee,
    })

# ── MEDIC ──────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def doctor_dashboard(request):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    now          = timezone.now()
    appointments = Appointment.objects.filter(doctor=request.user).select_related('patient')
    completed_count = appointments.filter(is_completed=True).count()
    pending_count   = appointments.filter(is_confirmed=False, is_completed=False, is_no_show=False).count()
    no_show_count   = appointments.filter(is_no_show=True).count()

    try:
        doctor_profile_obj = request.user.doctor_profile
        fee = float(doctor_profile_obj.consultation_fee)
    except DoctorProfile.DoesNotExist:
        doctor_profile_obj = None
        fee = 0

    # Venituri luna curenta
    revenue_private = 0
    revenue_cnas    = 0
    appts_this_month = appointments.filter(
        is_completed=True,
        date_time__month=now.month,
        date_time__year=now.year,
    )
    for a in appts_this_month:
        if a.cnas_covered:
            revenue_cnas += fee
        else:
            revenue_private += float(a.amount_paid) if a.amount_paid else fee

    revenue_total_month = revenue_private + revenue_cnas

    # Venituri totale
    all_completed = appointments.filter(is_completed=True).count()
    revenue_all_time = all_completed * fee

    return render(request, 'doctor_dashboard.html', {
        'appointments':        appointments,
        'doctor_profile':      doctor_profile_obj,
        'completed_count':     completed_count,
        'pending_count':       pending_count,
        'no_show_count':       no_show_count,
        'revenue_private':     int(revenue_private),
        'revenue_cnas':        int(revenue_cnas),
        'revenue_total_month': int(revenue_total_month),
        'revenue_all_time':    int(revenue_all_time),
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

    if request.method == 'POST':
        icd10   = request.POST.get('icd10_code', '').strip()
        appt.is_completed = True
        appt.is_confirmed = True
        appt.icd10_code   = icd10

        # Verificare CNAS: asigurat + bilet trimitere + cod ICD10
        try:
            pp = appt.patient.patient_profile
            if pp.is_insured and appt.referral_serial and icd10:
                appt.cnas_covered = True
                appt.cnas_code    = appt.generate_cnas_code()
                appt.amount_paid  = 0
                AuditLog.log(request, AuditLog.Action.CNAS_GENERATED,
                             metadata={'cnas_code': appt.cnas_code, 'appointment_id': appt.id})
        except PatientProfile.DoesNotExist:
            pass

        appt.save()
        AuditLog.log(request, AuditLog.Action.APPT_COMPLETED, metadata={'appointment_id': appointment_id})
        messages.success(request, 'Consultația a fost finalizată.')
        if appt.cnas_covered:
            messages.info(request, f'Decontare CNAS generată. Cod: {appt.cnas_code}')
    else:
        appt.is_completed = True
        appt.is_confirmed = True
        appt.save()

    return redirect('doctor_dashboard')


@login_required(login_url='login')
def mark_no_show(request, appointment_id):
    if not getattr(request.user, 'is_doctor', False):
        return redirect('home')
    appt = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    appt.is_no_show  = True
    appt.is_confirmed = True
    appt.save()
    AuditLog.log(request, AuditLog.Action.APPT_NO_SHOW, metadata={'appointment_id': appointment_id})
    messages.warning(request, f'Programarea lui {appt.patient.get_full_name() or appt.patient.username} marcată ca Neprezentare.')
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


#  ADMIN 

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