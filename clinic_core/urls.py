from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import (
    home_view, login_view, logout_view, register_view,
    patient_dashboard, cancel_appointment, profile_edit,
    profile_security, doctors_list, doctor_profile,
    new_appointment, rate_doctor, gdpr_export,
    doctor_dashboard, toggle_availability, doctor_profile_edit,
    approve_appointment, complete_appointment, delete_appointment,
    patient_history, add_prescription,
    admin_reports, admin_stats, admin_profile_edit,
)

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          home_view,     name='home'),
    path('login/',    login_view,    name='login'),
    path('logout/',   logout_view,   name='logout'),
    path('register/', register_view, name='register'),

    path('patient/dashboard/',                          patient_dashboard,  name='patient_dashboard'),
    path('patient/cancel/<int:appointment_id>/',        cancel_appointment, name='cancel_appointment'),
    path('patient/doctors/',                            doctors_list,       name='doctors_list'),
    path('patient/doctors/<int:doctor_id>/',            doctor_profile,     name='doctor_profile'),
    path('patient/new-appointment/<int:doctor_id>/',    new_appointment,    name='new_appointment'),
    path('patient/rate/<int:appointment_id>/',          rate_doctor,        name='rate_doctor'),
    path('patient/gdpr-export/',                        gdpr_export,        name='gdpr_export'),

    path('profile/edit/',     profile_edit,     name='profile_edit'),
    path('profile/security/', profile_security, name='profile_security'),

    path('doctor/dashboard/',                         doctor_dashboard,    name='doctor_dashboard'),
    path('doctor/profile/edit/',                      doctor_profile_edit, name='doctor_profile_edit'),
    path('doctor/toggle-availability/',               toggle_availability, name='toggle_availability'),
    path('doctor/approve/<int:appointment_id>/',      approve_appointment, name='approve_appointment'),
    path('doctor/complete/<int:appointment_id>/',     complete_appointment,name='complete_appointment'),
    path('doctor/delete/<int:appointment_id>/',       delete_appointment,  name='delete_appointment'),
    path('doctor/patient/<int:patient_id>/',          patient_history,     name='patient_history'),
    path('doctor/prescription/<int:appointment_id>/', add_prescription,    name='add_prescription'),

    path('admin-reports/',      admin_reports,      name='admin_reports'),
    path('admin-stats/',        admin_stats,        name='admin_stats'),
    path('admin-profile/edit/', admin_profile_edit, name='admin_profile_edit'),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
