__copyright__ = "Copyright 2017 Birkbeck, University of London"
__author__ = "Martin Paul Eve & Andy Byers"
__license__ = "AGPL v3"
__maintainer__ = "Birkbeck Centre for Technology and Publishing"

import datetime
from mock import patch

from django.core.management import call_command
from django.db import connection, IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from utils.testing import helpers
from core import models


class CoreTests(TestCase):
    """
    Regression tests for the core application.
    """

    @override_settings(URL_CONFIG="domain")
    def test_create_user_form(self):

        data = {
            'email': 'test@test.com',
            'is_active': True,
            'password_1': 'this_is_a_password',
            'password_2': 'this_is_a_password',
            'salutation': 'Prof.',
            'first_name': 'Martin',
            'last_name': 'Eve',
            'department': 'English & Humanities',
            'institution': 'Birkbeck, University of London',
            'country': 235,
        }

        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('core_add_user'), data)

        try:
            models.Account.objects.get(email='test@test.com')
        except models.Account.DoesNotExist:
            self.fail('User account has not been saved.')


    @override_settings(URL_CONFIG="domain")
    def test_create_user_form_mixed_case(self):
        data = {
            'email': 'test@test.com',
            'is_active': True,
            'password_1': 'this_is_a_password',
            'password_2': 'this_is_a_password',
            'salutation': 'Prof.',
            'first_name': 'Martin',
            'last_name': 'Eve',
            'department': 'English & Humanities',
            'institution': 'Birkbeck, University of London',
            'country': 235,
        }
        new_email = "TeSt@test.com"

        self.client.force_login(self.admin_user)
        response_1 = self.client.post(reverse('core_add_user'), data)
        response_2 = self.client.post(
            reverse('core_add_user'),
            dict(data, email=new_email),
        )

        try:
            models.Account.objects.get(email='test@test.com')
        except models.Account.DoesNotExist:
            self.fail('User account has not been saved.')

        self.assertEqual(response_2.status_code, 200)


    @override_settings(URL_CONFIG="domain")
    def test_create_user_form_normalise_email(self):

        data = {
            'email': 'Test@TEST.com',
            'is_active': True,
            'password_1': 'this_is_a_password',
            'password_2': 'this_is_a_password',
            'salutation': 'Prof.',
            'first_name': 'Martin',
            'last_name': 'Eve',
            'department': 'English & Humanities',
            'institution': 'Birkbeck, University of London',
            'country': 235,
        }

        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('core_add_user'), data)

        try:
            models.Account.objects.get(email='Test@test.com')
        except models.Account.DoesNotExist:
            self.fail('User account has not been saved.')

    @override_settings(URL_CONFIG="domain", CAPTCHA_TYPE=None)
    def test_mixed_case_email_address_correct_username(self):

        data = {
            'email': 'MiXeDcAsE@TEST.com',
            'is_active': True,
            'password_1': 'this_is_a_password',
            'password_2': 'this_is_a_password',
            'salutation': 'Prof.',
            'first_name': 'Martin',
            'last_name': 'Eve',
            'department': 'English & Humanities',
            'institution': 'Birkbeck, University of London',
            'country': '',
        }

        response = self.client.post(reverse('core_register'), data)
        try:
            models.Account.objects.get(username='mixedcase@test.com')
        except models.Account.DoesNotExist:
            self.fail('Username has not been set to lowercase.')

    @override_settings(URL_CONFIG="domain", CAPTCHA_TYPE=None)
    def test_mixed_case_email_address_no_duplicates(self):
        """Ensure no duplicate accounts can be created for mixed case emails"""
        email = "MiXeDcAsE@TEST.com"
        other_email = email.lower()

        data = {
            'email': email,
            'is_active': True,
            'password_1': 'this_is_a_password',
            'password_2': 'this_is_a_password',
            'salutation': 'Prof.',
            'first_name': 'Martin',
            'last_name': 'Eve',
            'department': 'English & Humanities',
            'institution': 'Birkbeck, University of London',
            'country': '',
        }

        response = self.client.post(reverse('core_register'), data)
        try:
            models.Account.objects.get(username='mixedcase@test.com')
        except models.Account.DoesNotExist:
            self.fail('Username has not been set to lowercase.')
        with self.assertRaises(
            IntegrityError,
            msg="Managed to issue accounts for %s and %s"
                "" % (email, other_email),
        ):
            models.Account.objects.create(email=other_email)


    @override_settings(URL_CONFIG="domain", CAPTCHA_TYPE=None)
    def test_mixed_case_login_same_case(self):
        email = "Janeway@voyager.com"
        password = "random_password"

        data = {
            'email': email,
            'is_active': True,
            'password_1': password,
            'password_2': password,
            'salutation': 'Prof.',
            'first_name': 'Martin',
            'last_name': 'Eve',
            'department': 'English & Humanities',
            'institution': 'Birkbeck, University of London',
            'country': '',
        }

        response = self.client.post(reverse('core_register'), data)
        account = models.Account.objects.get(email=email)
        account.is_active = True
        account.save()
        data = {"user_name": email, "user_pass": password}
        response = self.client.post(
            reverse("core_login"), data,
            HTTP_USER_AGENT='Mozilla/5.0',
        )
        self.assertEqual(
            self.client.session["_auth_user_id"], str(account.pk),
            msg="Registered user %s can't login with email %s"
                "" % (email, email),
        )

    @override_settings(URL_CONFIG="domain", CAPTCHA_TYPE=None)
    def test_mixed_case_login_different_case(self):
        email = "Janeway@voyager.com"
        login_email = email.lower()
        password = "random_password"

        data = {
            'email': email,
            'is_active': True,
            'password_1': password,
            'password_2': password,
            'salutation': 'Prof.',
            'first_name': 'Martin',
            'last_name': 'Eve',
            'department': 'English & Humanities',
            'institution': 'Birkbeck, University of London',
            'country': '',
        }

        response = self.client.post(reverse('core_register'), data)
        account = models.Account.objects.get(email=email)
        account.is_active = True
        account.save()
        data = {"user_name": login_email, "user_pass": password}
        response = self.client.post(
            reverse("core_login"), data,
            HTTP_USER_AGENT='Mozilla/5.0',
        )
        self.assertEqual(
            self.client.session["_auth_user_id"], str(account.pk),
            msg="Registered user %s can't login with email %s"
                "" % (email, login_email),
        )

    def test_email_subjects(self):
        email_settings= models.Setting.objects.filter(
            group__name="email",
        ).values_list("name", flat=True)
        subject_settings = models.Setting.objects.filter(
            group__name="email_subject",
        ).values_list("name", flat=True)
        missing = (
            set(email_settings)
            - {s[len("subject_"):] for s in subject_settings}
        )
        self.assertFalse(
            missing,
            msg="Found emails that don't have a subject setting")

    @patch.object(models.Setting, 'validate')
    def test_setting_validation(self, mock_method):
        from utils import setting_handler
        setting_handler.save_setting(
            'email', 'editor_assignment', self.journal_one, 'test'
        )
        mock_method.assert_called()

    def setUp(self):
        self.press = helpers.create_press()
        self.press.save()
        self.journal_one, self.journal_two = helpers.create_journals()
        helpers.create_roles(["editor", "author", "reviewer", "proofreader", "production", "copyeditor", "typesetter",
                            "proofing_manager", "section-editor"])

        self.regular_user = helpers.create_user("regularuser@martineve.com")
        self.regular_user.is_active = True
        self.regular_user.save()

        self.second_user = helpers.create_user("seconduser@martineve.com", ["reviewer"], journal=self.journal_one)
        self.second_user.is_active = True
        self.second_user.save()

        self.admin_user = helpers.create_user("adminuser@martineve.com")
        self.admin_user.is_staff = True
        self.admin_user.is_active = True
        self.admin_user.save()

        self.journal_one.name = 'Journal One'
        self.journal_two.name = 'Journal Two'
        call_command('install_plugins')
        call_command('load_default_settings')
