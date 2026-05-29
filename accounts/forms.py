from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from .models import CustomUser, Appointment, PatientProfile, Prescription, Payment

FA = {'class': 'form-input'}


class ClinicLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={**FA, 'placeholder': 'Nume utilizator', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={**FA, 'placeholder': 'Parolă'}))


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True,
        widget=forms.TextInput(attrs={**FA, 'placeholder': 'Prenume'}))
    last_name  = forms.CharField(max_length=50, required=True,
        widget=forms.TextInput(attrs={**FA, 'placeholder': 'Nume'}))
    email = forms.EmailField(required=True,
        widget=forms.EmailInput(attrs={**FA, 'placeholder': 'Adresă email'}))

    class Meta:
        model  = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {'username': forms.TextInput(attrs={**FA, 'placeholder': 'Nume utilizator'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({**FA, 'placeholder': 'Parolă'})
        self.fields['password2'].widget.attrs.update({**FA, 'placeholder': 'Confirmă parola'})
        for field in self.fields.values():
            field.help_text = None

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Există deja un cont cu această adresă.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_patient = True
        user.email      = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class AppointmentForm(forms.ModelForm):
    referral_serial = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={**FA, 'placeholder': 'Ex: BT-2024-001234'}),
        label='Serie bilet trimitere',
    )

    class Meta:
        model   = Appointment
        fields  = ['date_time', 'reason']
        widgets = {
            'date_time': forms.DateTimeInput(attrs={**FA, 'type': 'datetime-local'}),
            'reason':    forms.Textarea(attrs={**FA, 'rows': 3, 'placeholder': 'Motivul vizitei...'}),
        }

class PatientUserForm(forms.ModelForm):
    class Meta:
        model   = CustomUser
        fields  = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={**FA, 'placeholder': 'Prenume'}),
            'last_name':  forms.TextInput(attrs={**FA, 'placeholder': 'Nume'}),
            'email':      forms.EmailInput(attrs={**FA, 'placeholder': 'Email'}),
        }


class PatientProfileForm(forms.ModelForm):
    class Meta:
        model   = PatientProfile
        fields  = ['phone', 'cnp', 'birth_date', 'blood_type', 'allergies', 'is_insured', 'health_card_serial']
        widgets = {
            'phone':             forms.TextInput(attrs={**FA, 'placeholder': '07xx xxx xxx'}),
            'cnp':               forms.TextInput(attrs={**FA, 'placeholder': '13 cifre', 'maxlength': '13'}),
            'birth_date':        forms.DateInput(attrs={**FA, 'type': 'date'}),
            'blood_type':        forms.TextInput(attrs={**FA, 'placeholder': 'Ex: A+, O-, AB+'}),
            'allergies':         forms.Textarea(attrs={**FA, 'rows': 3, 'placeholder': 'Ex: penicilină, latex...'}),
            'health_card_serial':forms.TextInput(attrs={**FA, 'placeholder': 'Ex: 0004-1234-5678-9012'}),
        }
        labels = {
            'is_insured':         'Asigurat CNAS',
            'health_card_serial': 'Serie card de sănătate',
        }


class PrescriptionForm(forms.ModelForm):
    icd10_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={**FA, 'placeholder': 'Ex: J06, I10, E11 (opțional)'}),
        label='Cod ICD-10',
    )

    class Meta:
        model   = Prescription
        fields  = ['diagnosis', 'medication', 'instructions']
        widgets = {
            'diagnosis':    forms.Textarea(attrs={**FA, 'rows': 2, 'placeholder': 'Diagnostic...'}),
            'medication':   forms.Textarea(attrs={**FA, 'rows': 4, 'placeholder': 'Un medicament per linie\nEx: Amoxicilină 500mg - 3x/zi - 7 zile'}),
            'instructions': forms.Textarea(attrs={**FA, 'rows': 2, 'placeholder': 'Instrucțiuni suplimentare...'}),
        }
        labels = {
            'diagnosis':    'Diagnostic',
            'medication':   'Medicație prescrisă',
            'instructions': 'Instrucțiuni',
        }


class PaymentForm(forms.ModelForm):
    pay_for_patient = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_patient=True),
        required=False,
        empty_label='— Plătesc pentru mine —',
        label='Plătesc pentru alt pacient (aparținător)',
        widget=forms.Select(attrs={**FA}),
    )

    class Meta:
        model   = Payment
        fields  = ['method', 'note']
        widgets = {
            'method': forms.Select(attrs={**FA}),
            'note':   forms.TextInput(attrs={**FA, 'placeholder': 'Observații (opțional)'}),
        }
        labels = {
            'method': 'Metodă de plată',
            'note':   'Observații',
        }


class ClinicPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({**FA, 'placeholder': 'Parola actuală'})
        self.fields['new_password1'].widget.attrs.update({**FA, 'placeholder': 'Parola nouă'})
        self.fields['new_password2'].widget.attrs.update({**FA, 'placeholder': 'Confirmă parola nouă'})
        for field in self.fields.values():
            field.help_text = None