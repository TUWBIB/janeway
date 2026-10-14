from django.db import models

from journal import models as journal_models

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


class BulkJob(models.Model):

    BULKJOB_STATUS_NONE = ''
    BULKJOB_STATUS_STARTED = 'started'
    BULKJOB_STATUS_SUCCESS = 'success'
    BULKJOB_STATUS_ERROR = 'error'

    BULKJOB_STATUS_CHOICES = [
        (BULKJOB_STATUS_NONE, BULKJOB_STATUS_NONE),
        (BULKJOB_STATUS_STARTED, BULKJOB_STATUS_STARTED),
        (BULKJOB_STATUS_SUCCESS, BULKJOB_STATUS_SUCCESS),
        (BULKJOB_STATUS_ERROR, BULKJOB_STATUS_ERROR),
    ]
    journal = models.ForeignKey(
        "journal.Journal",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    jobid = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    data = models.TextField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=BULKJOB_STATUS_CHOICES,
    )

    data = models.TextField(
        blank=True,
        null=True,
    )
