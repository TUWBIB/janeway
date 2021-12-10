from django import forms

from submission import models
from core import models as core_models


class PublicationInfo(forms.ModelForm):
    class Meta:
        model = models.Article
        fields = ('date_accepted', 'date_published', 'page_numbers', 'primary_issue', 'peer_reviewed', 'render_galley')

    def __init__(self, *args, **kwargs):
        super(PublicationInfo, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            article = kwargs['instance']
            self.fields['primary_issue'].queryset = article.journal.issue_set.all()
            self.fields['render_galley'].queryset = article.galley_set.all()
            self.fields['date_accepted'].widget.attrs['class'] = 'datepicker'
            self.fields['date_published'].widget.attrs['class'] = 'datepicker'


class RemoteArticle(forms.ModelForm):
    class Meta:
        model = models.Article
        fields = ('is_remote', 'remote_url')


class RemoteParse(forms.Form):
    url = forms.CharField(required=True, label="Enter a URL or a DOI.")
    mode = forms.ChoiceField(required=True, choices=(('url', 'URL'), ('doi', 'DOI')))


class BackContentAuthorForm(forms.ModelForm):

    class Meta:
        model = core_models.Account
        exclude = (
            'date_joined',
            'activation_code'
            'date_confirmed'
            'confirmation_code'
            'reset_code'
            'reset_code_validated'
            'roles'
            'interest'
            'is_active'
            'is_staff'
            'is_admin'
            'password',
            'username',
            'roles',
        )

        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'middle_name': forms.TextInput(attrs={'placeholder': 'Middle name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name'}),
            'biography': forms.Textarea(
                attrs={'placeholder': 'Enter biography here'}),
            'institution': forms.TextInput(attrs={'placeholder': 'Institution'}),
            'department': forms.TextInput(attrs={'placeholder': 'Department'}),
            'twitter': forms.TextInput(attrs={'placeholder': 'Twitter handle'}),
            'linkedin': forms.TextInput(attrs={'placeholder': 'LinkedIn profile'}),
            'impactstory': forms.TextInput(attrs={'placeholder': 'ImpactStory profile'}),
            'orcid': forms.TextInput(attrs={'placeholder': 'ORCID ID'}),
            'gndid': forms.TextInput(attrs={'placeholder': 'GND ID'}),
            'email': forms.TextInput(attrs={'placeholder': 'Email address'}),

        }

    def __init__(self, *args, **kwargs):
        super(BackContentAuthorForm, self).__init__(*args, **kwargs)
        self.fields['password'].required = False
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['institution'].required = False
