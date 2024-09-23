import bleach
from django.forms import (
    CharField,
    CheckboxInput,
    ModelForm,
    DateInput,
    HiddenInput,
    Form,
)
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.exceptions import ValidationError

from modeltranslation import forms as mt_forms, translator
from captcha.fields import CaptchaField
from simplemathcaptcha.fields import MathCaptchaField
from hcaptcha.fields import hCaptchaField

from submission import models as submission_models


ENTITIES_MAP = (("&amp;", "&"), ("&gt;", ">"), ("&lt;", "<"))


class JanewayTranslationModelForm(mt_forms.TranslationModelForm):
    def __init__(self, *args, **kwargs):
        super(JanewayTranslationModelForm, self).__init__(*args, **kwargs)
        opts = translator.translator.get_options_for_model(self._meta.model)
        self.translated_field_names = opts.get_field_names()


class FakeModelForm(ModelForm):
    """ A form that can't be saved

    Usefull for rendering a sample form
    """

    def __init__(self, *args, disable_fields=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.disable_fields = disable_fields
        if disable_fields is True:
            for field in self.fields:
                self.fields[field].widget.attrs["readonly"] = True

    def save(self, *args, **kwargs):
        raise NotImplementedError("FakeModelForm can't be saved")

    def clean(self, *args, **kwargs):
        if self.disable_fields is True:
            raise NotImplementedError(
                "FakeModelForm can't be cleaned: disable_fields is True",
            )
        return super().clean(*args, **kwargs)


class KeywordModelForm(ModelForm):
    """ A ModelForm for models implementing a Keyword M2M relationship """
    keywords = CharField(
            required=False, help_text=_("Hit Enter to add a new keyword."))
    keywords_de = CharField(
            required=False, help_text=_("Hit Enter to add a new keyword."))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if hasattr(self.instance, 'keywords_lang_en'):
            current_keywords = self.instance.keywords_lang_en().values_list("word", flat=True)
            field = self.fields["keywords"]
            field.initial = ",".join(current_keywords)

        if hasattr(self.instance, 'keywords_lang_de'):
            current_keywords = self.instance.keywords_lang_de().values_list("word", flat=True)
            field = self.fields["keywords_de"]
            field.initial = ",".join(current_keywords)

    def save(self, commit=True, *args, **kwargs):
        posted_keywords = self.cleaned_data.get( 'keywords', '')

        instance = super().save(commit=commit, *args, **kwargs)
        instance.keywords.clear()

        # en keywords
        if 'keywords' in self.cleaned_data:
            posted_keywords = self.cleaned_data.get('keywords', '').split(',')
            for keyword in posted_keywords:
                if keyword != '':
                    obj, _ = submission_models.Keyword.objects.get_or_create(
                            word=keyword,
                            language='en',
                            )
                    instance.keywords.add(obj)

            for keyword in instance.keywords.filter(language='en'):
                if keyword.word not in posted_keywords:
                    instance.keywords.remove(keyword)

        # de keywords
        if 'keywords_de' in self.cleaned_data:
            posted_keywords = self.cleaned_data.get('keywords_de', '').split(',')
            for keyword in posted_keywords:
                if keyword != '':
                    obj, _ = submission_models.Keyword.objects.get_or_create(
                            word=keyword,
                            language='de',
                            )
                    instance.keywords.add(obj)

            for keyword in instance.keywords.filter(language='de'):
                if keyword.word not in posted_keywords:
                    instance.keywords.remove(keyword)

        if commit:
            instance.save()
        return instance


class HTMLDateInput(DateInput):
    input_type = 'date'

    def __init__(self, **kwargs):
        kwargs["format"] = "%Y-%m-%d"
        super().__init__(**kwargs)


class HTMLSwitchInput(CheckboxInput):
    template_name = 'admin/elements/forms/foundation_switch_input.html'


class CaptchaForm(Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Used by simple math captcha
        self.question_template = None

        if settings.CAPTCHA_TYPE == 'simple_math':
            self.question_template = _('What is %(num1)i %(operator)s %(num2)i? ')
            captcha = MathCaptchaField(label=_('Answer this question: '))
        elif settings.CAPTCHA_TYPE == 'hcaptcha':
            captcha = hCaptchaField()
        elif settings.CAPTCHA_TYPE == 'simple-captcha':
            captcha = CaptchaField()
        else:
            captcha = CharField(widget=HiddenInput, required=False)

        self.fields["captcha"] = captcha


def text_sanitizer(text_value, tags=None, attrs=None, excl=ENTITIES_MAP):
    """ A sanitizer for clearing potential harmful html/css/js from the input
    :param text_value: the string to sanitize
    :param tags: A list of allowed html tags
    :param attrs: A dict of allowed html attributes
    :param excl: A list of pairs of allowed items and their replacement
    :return: Sanitized string
    """
    tags = tags or []
    attrs = attrs or {}
    excl = excl or {}

    cleaned = bleach.clean(
        text_value,
        tags=tags,
        attributes=attrs,
        strip=True,
    )
    # Allow certain entities that bleach won't whitelist
    # https://github.com/mozilla/bleach/issues/192#issuecomment-2304545475
    for escaped, raw in excl:
        cleaned = cleaned.replace(escaped, raw)

    return cleaned


def plain_text_validator(value):
    """ A field validator that ensures a textual input has no harmful code"""
    sanitized = text_sanitizer(value)
    if value != sanitized:
        raise ValidationError(
            _("HTML is not allowed in this field")
        )
