from django.contrib import admin
from django.urls import path
from accounts.views import (
    home_view, login_view, logout_view, register_view,
    patient_dashboard, cancel_appointment, profile_edit,
    profile_security, doctors_list,
    doctor_dashboard, toggle_availability,
    approve_appointment, delete_appointment,
    patient_history, add_prescription,
    admin_reports,
)

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          home_view,     name='home'),
    path('login/',    login_view,    name='login'),
    path('logout/',   logout_view,   name='logout'),
    path('register/', register_view, name='register'),

    # Pacient
    path('patient/dashboard/',                   patient_dashboard,  name='patient_dashboard'),
    path('patient/cancel/<int:appointment_id>/', cancel_appointment, name='cancel_appointment'),
    path('patient/doctors/',                     doctors_list,       name='doctors_list'),

    # Profil (pacient + medic)
    path('profile/edit/',     profile_edit,     name='profile_edit'),
    path('profile/security/', profile_security, name='profile_security'),

    # Medic
    path('doctor/dashboard/',                        doctor_dashboard,    name='doctor_dashboard'),
    path('doctor/toggle-availability/',              toggle_availability, name='toggle_availability'),
    path('doctor/approve/<int:appointment_id>/',     approve_appointment, name='approve_appointment'),
    path('doctor/delete/<int:appointment_id>/',      delete_appointment,  name='delete_appointment'),
    path('doctor/patient/<int:patient_id>/',         patient_history,     name='patient_history'),
    path('doctor/prescription/<int:appointment_id>/',add_prescription,    name='add_prescription'),

    # Admin
    path('admin-reports/', admin_reports, name='admin_reports'),
]
