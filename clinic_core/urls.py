from django.contrib import admin
from django.urls import path
from accounts.views import (
    home_view, login_view, logout_view, register_view,
    patient_dashboard, cancel_appointment, profile_edit, doctors_list,
    doctor_dashboard, approve_appointment, delete_appointment,
)

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          home_view,     name='home'),
    path('login/',    login_view,    name='login'),
    path('logout/',   logout_view,   name='logout'),
    path('register/', register_view, name='register'),

    path('patient/dashboard/',                      patient_dashboard,   name='patient_dashboard'),
    path('patient/cancel/<int:appointment_id>/',    cancel_appointment,  name='cancel_appointment'),
    path('patient/doctors/',                        doctors_list,        name='doctors_list'),
    path('profile/edit/',                           profile_edit,        name='profile_edit'),

    path('doctor/dashboard/',                       doctor_dashboard,    name='doctor_dashboard'),
    path('doctor/approve/<int:appointment_id>/',    approve_appointment, name='approve_appointment'),
    path('doctor/delete/<int:appointment_id>/',     delete_appointment,  name='delete_appointment'),
]
