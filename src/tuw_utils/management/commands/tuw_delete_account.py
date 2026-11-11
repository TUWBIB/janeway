import re

from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils.translation import activate
from django.utils import translation
from django.conf import settings
from django.db import connection, transaction
from django.db import models
from django.db.models import Q

from core import models as core_models

class Command(BaseCommand):
    """A management command to set articles back to unassigned stage (post submission)."""

    help = "Sets articles back to unassigned."

    def add_arguments(self, parser):
        """ Adds arguments to Django's management command-line parser.

        :param parser: the parser to which the required arguments will be added
        :return: None
        """
        parser.add_argument('--minpk', default=1)
        parser.add_argument('--maxpk', default=99999)
        parser.add_argument('--excludepk', default='')
        parser.add_argument('--pattern', default='no_matching_pattern')

    def trace_with_counts(self, model, to_delete_qs, seen=None):

        def _incoming_fks(model):
            for candidate in apps.get_models():
                for f in candidate._meta.get_fields():
                    if isinstance(f, models.ForeignKey) and f.related_model is model:
                        yield candidate, f

        seen = seen if seen is not None else set()
        if model in seen:
            return
        seen.add(model)

        # ids of the rows you're about to delete
        ids = to_delete_qs.values_list("pk", flat=True)
        for child, fk in _incoming_fks(model):
            effect = fk.remote_field.on_delete
            reverse = fk.remote_field.get_accessor_name()
            child_qs = child.objects.filter(**{f"{fk.name}__in": ids})

            if effect is models.CASCADE:
                print(f"  CASCADE     -> {child.__name__} (via {reverse}): {child_qs.count()} row(s) deleted")
                self.trace_with_counts(child, child_qs, seen)
            elif effect in (models.PROTECT, models.RESTRICT):
                n = child_qs.count()
                flag = " BLOCKS DELETION" if n else ""
                print(f"  {getattr(effect,'__name__','SET'):11}-> {child.__name__} (via {reverse}): {n} row(s) referenced{flag}")
            else:
                print(f"  {getattr(effect,'__name__','SET'):11}-> {child.__name__} (via {reverse}): {child_qs.count()} row(s) FK updated")

    def handle(self, *args, **options):
        article: submission_models.Article

        minpk = options.get('minpk', 1)
        maxpk = options.get('maxpk', 99999)
        excludepk = options.get('excludepk', '')
        l_excluded = [int(x) for x in excludepk.split(',')] if excludepk else []
        pattern = options.get('pattern', 'no_matching_pattern')

        related_objects = core_models.Account._meta.related_objects
        for relation in related_objects:
            # Get the target model class and its database table name
            target_model = relation.related_model
            table_name = target_model._meta.db_table
            field_name = relation.field.name
            print(f"Table: {table_name} | Model: {target_model.__name__} (via field: {field_name})")

        accounts = core_models.Account.objects.filter(pk__gte=minpk,pk__lte=maxpk).order_by('id')
        for account in accounts:
            print (f"processing account {account.pk} {account.email}")

            if account.pk in l_excluded:
                print("skipped, in exclude list")
                continue
            
            if not (match := re.search(pattern,account.email)):
                print("skipped, email pattern not matching")
                continue

            to_delete = core_models.Account.objects.filter(pk=account.pk)   # <-- your known field + value
            print(f"Deleting {to_delete.count()} row(s) of {core_models.Account.__name__}")
            self.trace_with_counts(core_models.Account, to_delete)

            account.delete()



# Table: core_passwordresettoken | Model: PasswordResetToken (via field: account)
# Table: core_accountrole | Model: AccountRole (via field: user)
# Table: core_file | Model: File (via field: owner)
# Table: core_filehistory | Model: FileHistory (via field: owner)
# Table: core_task | Model: Task (via field: completed_by)
# Table: core_task | Model: Task (via field: assignees)
# Table: core_editorialgroupmember | Model: EditorialGroupMember (via field: user)
# Table: core_accessrequest | Model: AccessRequest (via field: user)
# Table: copyediting_copyeditassignment | Model: CopyeditAssignment (via field: copyeditor)
# Table: copyediting_copyeditassignment | Model: CopyeditAssignment (via field: editor)
# Table: copyediting_authorreview | Model: AuthorReview (via field: author)
# Table: discussion_thread | Model: Thread (via field: owner)
# Table: discussion_post | Model: Post (via field: owner)
# Table: discussion_post | Model: Post (via field: read_by)
# Table: journal_issue | Model: Issue (via field: editors)
# Table: journal_issueeditor | Model: IssueEditor (via field: account)
# Table: journal_prepublicationchecklistitem | Model: PrePublicationChecklistItem (via field: completed_by)
# Table: journal_notifications | Model: Notifications (via field: user)
# Table: comms_newsitem | Model: NewsItem (via field: posted_by)
# Table: press_staffgroupmember | Model: StaffGroupMember (via field: user)
# Table: production_productionassignment | Model: ProductionAssignment (via field: production_manager)
# Table: production_productionassignment | Model: ProductionAssignment (via field: editor)
# Table: production_typesettask | Model: TypesetTask (via field: typesetter)
# Table: proofing_proofingassignment | Model: ProofingAssignment (via field: proofing_manager)
# Table: proofing_proofingassignment | Model: ProofingAssignment (via field: editor)
# Table: proofing_proofingtask | Model: ProofingTask (via field: proofreader)
# Table: proofing_typesetterproofingtask | Model: TypesetterProofingTask (via field: typesetter)
# Table: proofing_note | Model: Note (via field: creator)
# Table: review_editorassignment | Model: EditorAssignment (via field: editor)
# Table: review_reviewassignment | Model: ReviewAssignment (via field: reviewer)
# Table: review_reviewassignment | Model: ReviewAssignment (via field: editor)
# Table: review_reviewerrating | Model: ReviewerRating (via field: rater)
# Table: review_revisionaction | Model: RevisionAction (via field: user)
# Table: review_revisionrequest | Model: RevisionRequest (via field: editor)
# Table: review_editoroverride | Model: EditorOverride (via field: editor)
# Table: review_decisiondraft | Model: DecisionDraft (via field: editor)
# Table: review_decisiondraft | Model: DecisionDraft (via field: section_editor)
# Table: repository_repository | Model: Repository (via field: managers)
# Table: repository_repository | Model: Repository (via field: submission_notification_recipients)
# Table: repository_repositoryrole | Model: RepositoryRole (via field: user)
# Table: repository_preprint | Model: Preprint (via field: owner)
# Table: repository_preprintauthor | Model: PreprintAuthor (via field: account)
# Table: repository_comment | Model: Comment (via field: author)
# Table: repository_subject | Model: Subject (via field: editors)
# Table: repository_review | Model: Review (via field: manager)
# Table: repository_review | Model: Review (via field: reviewer)
# Table: submission_publishernote | Model: PublisherNote (via field: creator)
# Table: submission_article | Model: Article (via field: owner)
# Table: submission_article | Model: Article (via field: correspondence_author)
# Table: submission_article | Model: Article (via field: authors)
# Table: submission_frozenauthor | Model: FrozenAuthor (via field: author)
# Table: submission_section | Model: Section (via field: editors)
# Table: submission_section | Model: Section (via field: section_editors)
# Table: submission_note | Model: Note (via field: creator)
# Table: submission_articleauthororder | Model: ArticleAuthorOrder (via field: author)
# Table: utils_logentry | Model: LogEntry (via field: actor)
# Table: typesetting_typesettingclaim | Model: TypesettingClaim (via field: editor)
# Table: typesetting_typesettingassignment | Model: TypesettingAssignment (via field: manager)
# Table: typesetting_typesettingassignment | Model: TypesettingAssignment (via field: typesetter)
# Table: typesetting_galleyproofing | Model: GalleyProofing (via field: manager)
# Table: typesetting_galleyproofing | Model: GalleyProofing (via field: proofreader)
# Table: featured_featuredarticle | Model: FeaturedArticle (via field: added_by)
# 
# 
# 
# 
# 
#     
