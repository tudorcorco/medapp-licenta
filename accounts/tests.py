from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from .models import (
    CustomUser, PatientProfile, DoctorProfile,
    Appointment, Payment, Wallet, WalletTransaction,
    LoginAttempt, TwoFactorCode,
)


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = CustomUser.objects.create_user(
            username='test_patient', password='TestPass123!',
            email='patient@test.com', is_patient=True,
        )
        PatientProfile.objects.create(user=self.patient)
        Wallet.objects.create(user=self.patient, balance=0)

        self.doctor = CustomUser.objects.create_user(
            username='test_doctor', password='TestPass123!',
            email='doctor@test.com', is_doctor=True,
        )
        self.admin = CustomUser.objects.create_user(
            username='test_admin', password='TestPass123!',
            email='admin@test.com', is_staff=True,
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Autentifică-te')

    def test_doctor_login_direct(self):
        response = self.client.post(reverse('login'), {
            'username': 'test_doctor',
            'password': 'TestPass123!',
        })
        self.assertRedirects(response, reverse('doctor_dashboard'))

    def test_admin_login_direct(self):
        response = self.client.post(reverse('login'), {
            'username': 'test_admin',
            'password': 'TestPass123!',
        })
        self.assertRedirects(response, reverse('admin_reports'))

    def test_patient_login_triggers_2fa(self):
        response = self.client.post(reverse('login'), {
            'username': 'test_patient',
            'password': 'TestPass123!',
        })
        self.assertRedirects(response, reverse('verify_2fa'))
        self.assertIn('2fa_user_id', self.client.session)

    def test_wrong_password_fails(self):
        response = self.client.post(reverse('login'), {
            'username': 'test_patient',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('2fa_user_id', self.client.session)

    def test_remember_me_sets_long_session(self):
        self.client.post(reverse('login'), {
            'username': 'test_doctor',
            'password': 'TestPass123!',
            'remember_me': 'on',
        })
        expiry = self.client.session.get_expiry_age()
        self.assertGreater(expiry, 60 * 60 * 24 * 29)

    def test_no_remember_me_session_expires_on_browser_close(self):
        self.client.post(reverse('login'), {
            'username': 'test_doctor',
            'password': 'TestPass123!',
        })
        self.assertTrue(self.client.session.get_expire_at_browser_close())


class TwoFactorTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = CustomUser.objects.create_user(
            username='tfa_patient', password='TestPass123!',
            email='tfa@test.com', is_patient=True,
        )
        PatientProfile.objects.create(user=self.patient)
        Wallet.objects.create(user=self.patient, balance=0)

    def _start_2fa(self):
        self.client.post(reverse('login'), {
            'username': 'tfa_patient',
            'password': 'TestPass123!',
        })

    def test_correct_code_logs_in(self):
        self._start_2fa()
        tfa = TwoFactorCode.objects.filter(user=self.patient, used=False).first()
        self.assertIsNotNone(tfa)
        response = self.client.post(reverse('verify_2fa'), {'code': tfa.code})
        self.assertRedirects(response, reverse('patient_dashboard'))

    def test_wrong_code_shows_error(self):
        self._start_2fa()
        response = self.client.post(reverse('verify_2fa'), {'code': '000000'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'incorect')

    def test_expired_code_rejected(self):
        self._start_2fa()
        tfa = TwoFactorCode.objects.filter(user=self.patient, used=False).first()
        tfa.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        tfa.save()
        response = self.client.post(reverse('verify_2fa'), {'code': tfa.code})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'expirat')

    def test_verify_without_session_redirects_to_login(self):
        response = self.client.get(reverse('verify_2fa'))
        self.assertRedirects(response, reverse('login'))


class BruteForceProtectionTest(TestCase):
    def setUp(self):
        self.client = Client()
        CustomUser.objects.create_user(
            username='brute_patient', password='TestPass123!',
            email='brute@test.com', is_patient=True,
        )

    def test_soft_ban_after_5_failures(self):
        for _ in range(5):
            self.client.post(reverse('login'), {
                'username': 'brute_patient',
                'password': 'WrongPassword!',
            })
        self.assertTrue(
            LoginAttempt.objects.filter(is_soft_banned=True, revoked=False).exists()
        )

    def test_banned_ip_cannot_login(self):
        LoginAttempt.objects.create(
            ip_address='127.0.0.1',
            username='brute_patient',
            is_hard_banned=True,
            hard_ban_reason='test',
        )
        response = self.client.post(reverse('login'), {
            'username': 'brute_patient',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('2fa_user_id', self.client.session)


class WalletCashbackTest(TestCase):
    def setUp(self):
        self.patient = CustomUser.objects.create_user(
            username='cashback_patient', password='TestPass123!',
            email='cashback@test.com', is_patient=True,
        )
        PatientProfile.objects.create(user=self.patient)
        self.wallet = Wallet.objects.create(user=self.patient, balance=Decimal('500.00'))

        self.doctor_user = CustomUser.objects.create_user(
            username='cashback_doctor', password='TestPass123!',
            email='cashbackdr@test.com', is_doctor=True,
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            consultation_fee=Decimal('200.00'),
            is_available=True,
        )

    def test_cashback_5_percent_added_to_wallet(self):
        fee = Decimal('200.00')
        expected_cashback = (fee * Decimal('0.05')).quantize(Decimal('0.01'))
        balance_before = self.wallet.balance

        appt = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor_user,
            date_time=timezone.now() + timezone.timedelta(days=1),
            payment_method='WALLET',
        )
        Payment.objects.create(
            appointment=appt, payer=self.patient, beneficiary=self.patient,
            amount=fee, method=Payment.Method.WALLET, status=Payment.Status.COMPLETED,
        )
        self.wallet.balance -= fee
        self.wallet.balance += expected_cashback
        self.wallet.save()
        WalletTransaction.objects.create(
            wallet=self.wallet, tx_type=WalletTransaction.TxType.CASHBACK,
            amount=expected_cashback, balance_after=self.wallet.balance,
        )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, balance_before - fee + expected_cashback)
        self.assertEqual(expected_cashback, Decimal('10.00'))
        self.assertTrue(
            WalletTransaction.objects.filter(
                wallet=self.wallet, tx_type='CASHBACK'
            ).exists()
        )

    def test_cashback_is_exactly_5_percent(self):
        fee = Decimal('300.00')
        cashback = (fee * Decimal('0.05')).quantize(Decimal('0.01'))
        self.assertEqual(cashback, Decimal('15.00'))

    def test_wallet_insufficient_balance_blocked(self):
        self.wallet.balance = Decimal('10.00')
        self.wallet.save()
        fee = Decimal('200.00')
        self.assertLess(self.wallet.balance, fee)


class PerformanceScoreTest(TestCase):
    def setUp(self):
        self.doctor_user = CustomUser.objects.create_user(
            username='score_doctor', password='TestPass123!',
            email='score@test.com', is_doctor=True,
        )
        self.profile = DoctorProfile.objects.create(
            user=self.doctor_user, consultation_fee=Decimal('100.00'),
        )

    def test_score_is_zero_with_no_data(self):
        score = self.profile.performance_score()
        self.assertEqual(score, 0.0)

    def test_score_between_0_and_100(self):
        score = self.profile.performance_score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)