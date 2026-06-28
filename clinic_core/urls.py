from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import (
    home_view, login_view, logout_view, register_view, verify_2fa,
    patient_dashboard, cancel_appointment, profile_edit,
    profile_security, doctors_list, doctor_profile,
    new_appointment, rate_doctor, gdpr_export,
    doctor_dashboard, toggle_availability, doctor_profile_edit,
    approve_appointment, complete_appointment, delete_appointment,
    patient_history, add_prescription,
    admin_reports, admin_stats, admin_profile_edit, revoke_ban, confirm_cash_payment,
    payment_view, wallet_topup, mark_no_show,
    wallet_checkout, wallet_topup_card, card_checkout,
    receipt_view, receipt_pdf, dismiss_notification,doctor_calendar, beneficiary_view, toggle_language
)

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('',          home_view,     name='home'),
    path('login/',          login_view,    name='login'),
    path('login/verify/',   verify_2fa,    name='verify_2fa'),
    path('logout/',         logout_view,   name='logout'),
    path('register/',       register_view, name='register'),

    path('patient/dashboard/',                          patient_dashboard,  name='patient_dashboard'),
    path('patient/cancel/<int:appointment_id>/',        cancel_appointment, name='cancel_appointment'),
    path('patient/doctors/',                            doctors_list,       name='doctors_list'),
    path('patient/doctors/<int:doctor_id>/',            doctor_profile,     name='doctor_profile'),
    path('patient/new-appointment/<int:doctor_id>/',    new_appointment,    name='new_appointment'),
    path('patient/rate/<int:appointment_id>/',          rate_doctor,        name='rate_doctor'),
    path('patient/gdpr-export/',                        gdpr_export,        name='gdpr_export'),
    path('patient/payment/<int:appointment_id>/',       payment_view,       name='payment_view'),

    
    path('patient/card-checkout/<int:appointment_id>/', card_checkout,      name='card_checkout'),
    path('patient/receipt/<int:appointment_id>/',       receipt_view,       name='receipt_view'),
    path('patient/receipt/<int:appointment_id>/pdf/',   receipt_pdf,        name='receipt_pdf'),

    
    path('patient/wallet/topup/',                       wallet_topup,       name='wallet_topup'),
    path('patient/wallet/topup/card/',                  wallet_topup_card,  name='wallet_topup_card'),
    path('patient/wallet/checkout/<int:appointment_id>/', wallet_checkout,  name='wallet_checkout'),

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
    path('doctor/no-show/<int:appointment_id>/',      mark_no_show,        name='mark_no_show'),

    path('admin-reports/',         admin_reports,      name='admin_reports'),
    path('admin-stats/',           admin_stats,        name='admin_stats'),
    path('admin-profile/edit/',    admin_profile_edit, name='admin_profile_edit'),
    path('admin-security/revoke/<int:ban_id>/', revoke_ban, name='revoke_ban'),
    path('admin-cash/confirm/<int:payment_id>/', confirm_cash_payment, name='confirm_cash_payment'),
    path('patient/notification/dismiss/<int:appointment_id>/', 
     dismiss_notification, 
     name='dismiss_notification'),
     
    path('doctor/calendar/', doctor_calendar, name='doctor_calendar'),
    path('doctor/beneficiary/<int:appointment_id>/', beneficiary_view, name='beneficiary_view'),
    path('toggle-language/', toggle_language, name='toggle_language'),
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)