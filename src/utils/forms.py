from django.forms import CharField, ModelForm, DateInput
from django.utils.translation import gettext_lazy as _

from modeltranslation import forms as mt_forms, translator

from submission import models as submission_models


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
        instance = super().save(commit=commit, *args, **kwargs)

        # en keywords
        if 'keywords' in self.cleaned_data:
            posted_keywords = self.cleaned_data.get('keywords', '').split(',')
            for keyword in posted_keywords:
                print (keyword)
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
            print ("*** B")
            posted_keywords = self.cleaned_data.get('keywords_de', '').split(',')
            for keyword in posted_keywords:
                print (keyword)
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
