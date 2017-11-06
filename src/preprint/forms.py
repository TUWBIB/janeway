from django import forms
from django.utils.translation import ugettext_lazy as _
from django_summernote.widgets import SummernoteWidget

from submission import models as submission_models
from preprint import models
from press import models as press_models


class PreprintInfo(forms.ModelForm):
    keywords = forms.CharField(required=False)
    subject = forms.ModelChoiceField(required=True, queryset=models.Subject.objects.filter(enabled=True))

    class Meta:
        model = submission_models.Article
        fields = ('title', 'subtitle', 'abstract', 'language', 'license', 'comments_editor')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': _('Title')}),
            'subtitle': forms.TextInput(attrs={'placeholder': _('Subtitle')}),
            'abstract': forms.Textarea(
                attrs={'placeholder': _('Enter your article\'s abstract here')}),
        }

    def __init__(self, *args, **kwargs):
        super(PreprintInfo, self).__init__(*args, **kwargs)

        self.fields['license'].queryset = submission_models.Licence.objects.filter(press__isnull=False,
                                                                                   available_for_submission=True)
        self.fields['license'].required = True

        # If there is an instance, we want to try to set the default subject area
        if 'instance' in kwargs:
            article = kwargs['instance']
            if article:
                self.fields['subject'].initial = article.get_subject_area()

    def save(self, commit=True, request=None):
        article = super(PreprintInfo, self).save()

        posted_keywords = self.cleaned_data['keywords'].split(',')
        for keyword in posted_keywords:
            new_keyword, c = submission_models.Keyword.objects.get_or_create(word=keyword)
            article.keywords.add(new_keyword)

        for keyword in article.keywords.all():
            if keyword.word not in posted_keywords:
                article.keywords.remove(keyword)

        if self.cleaned_data.get('subject', None):
            article.set_preprint_subject(self.cleaned_data['subject'])

        return article


class CommentForm(forms.ModelForm):
    class Meta:
        model = models.Comment
        fields = ('body',)


class SettingsForm(forms.ModelForm):
    class Meta:
        model = press_models.Press
        fields = ('preprints_about', 'preprint_start', 'preprint_submission', 'preprint_publication',
                  'preprint_pdf_only',)
        widgets = {
            'preprints_about': SummernoteWidget,
            'preprint_start': SummernoteWidget,
            'preprint_submission': SummernoteWidget,
            'preprint_publication': SummernoteWidget,
        }

    def __init__(self, *args, **kwargs):
        super(SettingsForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            press = kwargs['instance']
            settings = press_models.PressSetting.objects.filter(press=press)

            for setting in settings:
                if setting.is_boolean:
                    self.fields[setting.name] = forms.BooleanField(widget=forms.CheckboxInput(), required=False)
                else:
                    self.fields[setting.name] = forms.CharField(widget=forms.TextInput(), required=False)
                self.fields[setting.name].initial = setting.value

    def save(self, commit=True):
        press = super(SettingsForm, self).save()
        settings = press_models.PressSetting.objects.filter(press=press)

        for setting in settings:
            if setting.is_boolean:
                setting.value = 'On' if self.cleaned_data[setting.name] else ''
            else:
                setting.value = self.cleaned_data[setting.name]
            setting.save()


class SubjectForm(forms.ModelForm):

    class Meta:
        model = models.Subject
        exclude = ('preprints',)
