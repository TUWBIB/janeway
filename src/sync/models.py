from django.db import models

# Create your models here.

class DataCite(models.Model):

    DATACITE_STATUS_NONE=''
    DATACITE_STATUS_DRAFT='draft'
    DATACITE_STATUS_FINDABLE='findable'
    DATACITE_STATUS_REGISTERED='registered'


    DATACITE_STATUS_CHOICES = [
        (DATACITE_STATUS_NONE, DATACITE_STATUS_NONE),
        (DATACITE_STATUS_NONE, DATACITE_STATUS_DRAFT),
        (DATACITE_STATUS_FINDABLE, DATACITE_STATUS_FINDABLE),
        (DATACITE_STATUS_REGISTERED, DATACITE_STATUS_REGISTERED),
    ]

    article = models.ForeignKey(
        'submission.Article',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    issue = models.ForeignKey(
        'journal.Issue',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=20, blank=True, null=True, choices=DATACITE_STATUS_CHOICES)
    ts = models.DateTimeField(blank=True, null=True)

class Alma(models.Model):
    article = models.ForeignKey(
        'submission.Article',
        on_delete=models.CASCADE,
        null=True,
    )

    issue = models.ForeignKey(
        'journal.Issue',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    mmsid = models.CharField(max_length=50, blank=True, null=True,)
    ac = models.CharField(max_length=50, blank=True, null=True,)


