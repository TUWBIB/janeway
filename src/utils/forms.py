from django.forms import CharField, ModelForm, DateInput
from django.utils.translation import gettext_lazy as _

from submission import models as submission_models


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

        if hasattr(self.instance, 'keywords'):
            current_keywords = self.instance.keywords.values_list("word", flat=True)
            field = self.fields["keywords"]
            field.initial = ",".join(current_keywords)

        if hasattr(self.instance, 'keywords_de'):
            current_keywords_de = self.instance.keywords_de.values_list("word", flat=True)
            field = self.fields["keywords_de"]
            field.initial = ",".join(current_keywords_de)


    def save(self, commit=True, *args, **kwargs):
        instance = super().save(commit=commit, *args, **kwargs)

        if 'keywords' in self.cleaned_data:
            posted_keywords = self.cleaned_data.get('keywords', '').split(',')
            for keyword in posted_keywords:
                if keyword != '':
                    obj, _ = submission_models.Keyword.objects.get_or_create(
                            word=keyword)
                    instance.keywords.add(obj)

            for keyword in instance.keywords.all():
                if keyword.word not in posted_keywords:
                    instance.keywords.remove(keyword)


        if 'keywords_de' in self.cleaned_data:
            posted_keywords_de = self.cleaned_data.get('keywords_de', '').split(',')
            for keyword_de in posted_keywords_de:
                if keyword_de != '':
                    obj, _ = submission_models.KeywordDe.objects.get_or_create(
                            word=keyword_de)
                    instance.keywords_de.add(obj)

            for keyword_de in instance.keywords_de.all():
                if keyword_de.word not in posted_keywords_de:
                    instance.keywords_de.remove(keyword_de)

        if commit:
            instance.save()
        return instance


class HTMLDateInput(DateInput):
    input_type = 'date'

    def __init__(self, **kwargs):
        kwargs["format"] = "%Y-%m-%d"
        super().__init__(**kwargs)
