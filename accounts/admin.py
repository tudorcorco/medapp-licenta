from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, PatientProfile, DoctorProfile, Appointment, AuditLog


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display  = ('username', 'email', 'is_patient', 'is_doctor', 'is_staff', 'is_active')
    list_filter   = ('is_patient', 'is_doctor', 'is_staff')
    fieldsets     = UserAdmin.fieldsets + (
        ('Roluri Clinică', {'fields': ('is_patient', 'is_doctor', 'is_admin')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Roluri Clinică', {'fields': ('is_patient', 'is_doctor', 'is_admin')}),
    )


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'cnp', 'blood_type', 'phone')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'consultation_fee', 'is_available')


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'date_time', 'is_confirmed')
    list_filter  = ('is_confirmed',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('timestamp', 'user', 'action', 'ip_address')
    list_filter   = ('action',)
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'metadata', 'timestamp')

    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
