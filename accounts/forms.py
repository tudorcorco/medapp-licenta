from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser, Appointment, PatientProfile

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
    class Meta:
        model   = Appointment
        fields  = ['doctor', 'date_time', 'reason']
        widgets = {
            'date_time': forms.DateTimeInput(attrs={**FA, 'type': 'datetime-local'}),
            'reason':    forms.Textarea(attrs={**FA, 'rows': 3, 'placeholder': 'Motivul vizitei...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['doctor'].queryset = CustomUser.objects.filter(is_doctor=True)
        self.fields['doctor'].widget.attrs.update(FA)
        self.fields['doctor'].label = 'Selectează medicul'


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
        fields  = ['phone', 'cnp', 'birth_date', 'blood_type', 'allergies']
        widgets = {
            'phone':      forms.TextInput(attrs={**FA, 'placeholder': '07xx xxx xxx'}),
            'cnp':        forms.TextInput(attrs={**FA, 'placeholder': '13 cifre', 'maxlength': '13'}),
            'birth_date': forms.DateInput(attrs={**FA, 'type': 'date'}),
            'blood_type': forms.TextInput(attrs={**FA, 'placeholder': 'Ex: A+, O-, AB+'}),
            'allergies':  forms.Textarea(attrs={**FA, 'rows': 3, 'placeholder': 'Ex: penicilină, latex...'}),
        }
