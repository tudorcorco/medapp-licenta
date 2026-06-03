from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, PatientProfile, DoctorProfile,
    Appointment, Prescription, Rating,
    Wallet, WalletTransaction, Payment, AuditLog, LoginAttempt,
)


admin.site.site_header = 'Portal MedApp'
admin.site.site_title  = 'Panou de Control Securitate'
admin.site.index_title = 'Administrare MedApp'


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display  = ('ip_address', 'username', 'timestamp', 'is_soft_banned', 'is_hard_banned', 'revoked')
    list_filter   = ('is_soft_banned', 'is_hard_banned', 'revoked')
    search_fields = ('ip_address', 'username')
    readonly_fields = ('timestamp', 'revoked_at', 'revoked_by')
    ordering      = ('-timestamp',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('user', 'action', 'ip_address', 'timestamp')
    list_filter   = ('action',)
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'metadata', 'timestamp')
    ordering      = ('-timestamp',)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_role_label', 'is_active', 'date_joined')
    list_filter  = ('is_patient', 'is_doctor', 'is_admin', 'is_staff', 'is_active')
    fieldsets    = UserAdmin.fieldsets + (
        ('Rol MedApp', {'fields': ('is_patient', 'is_doctor', 'is_admin')}),
    )


admin.site.register(PatientProfile)
admin.site.register(DoctorProfile)
admin.site.register(Appointment)
admin.site.register(Prescription)
admin.site.register(Rating)
admin.site.register(Wallet)
admin.site.register(WalletTransaction)
admin.site.register(Payment)