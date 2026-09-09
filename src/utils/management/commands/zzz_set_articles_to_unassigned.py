from io import BytesIO

from django.core.management.base import BaseCommand
from django.utils.translation import activate
from django.utils import translation
from django.conf import settings
from django.db import connection, transaction

from submission import models as submission_models
from journal import models as journal_models
from review import models as review_models
from copyediting import models as copyediting_models
from production import models as production_models
from proofing import models as proofing_models
from core import models as core_models
from cron import models as cron_models
from discussion import models as discussion_models
from metrics import models as metrics_models
from press import models as press_models
from repository import models as repository_models
from core.homepage_elements.carousel import models as carousel_models
from core.homepage_elements.featured import models as feautured_models
from plugins.typesetting import models as typesetting_models

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

    def handle(self, *args, **options):
        article: submission_models.Article

        minpk = options.get('minpk', 1)
        maxpk = options.get('maxpk', 99999)

        related_objects = submission_models.Article._meta.related_objects
        for relation in related_objects:
            # Get the target model class and its database table name
            target_model = relation.related_model
            table_name = target_model._meta.db_table
            field_name = relation.field.name
            print(f"Table: {table_name} | Model: {target_model.__name__} (via field: {field_name})")

        articles = submission_models.Article.objects.filter(pk__gte=minpk,pk__lte=maxpk).order_by('id')
        for article in articles:
            print (f"processing article {article.pk}")

            article.stage =  submission_models.STAGE_UNASSIGNED
            article.date_accepted = None
            article.date_declined = None
            # article.date_submitted = None
            article.date_published = None
            article.date_updated = None
            article.save() 

            print("deleted %d from %s", (res := review_models.EditorAssignment.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := review_models.ReviewRound.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := review_models.ReviewAssignment.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := review_models.RevisionRequest.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := review_models.EditorOverride.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := review_models.DecisionDraft.objects.filter(article=article)).delete()[0], res.model.__name__)

            print("deleted %d from %s", (res := copyediting_models.CopyeditAssignment.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := production_models.ProductionAssignment.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := proofing_models.ProofingAssignment.objects.filter(article=article)).delete()[0], res.model.__name__)
            
            print("deleted %d from %s", (res := typesetting_models.TypesettingClaim.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := typesetting_models.TypesettingRound.objects.filter(article=article)).delete()[0], res.model.__name__)

#            print("deleted %d from %s", (res := carousel_models.Carousel.objects.filter(article=article)).delete()[0], res.model.__name__)
#            print("deleted %d from %s", (res := carousel_models.CarouselObject.objects.filter(article=article)).delete()[0], res.model.__name__)

            print("deleted %d from %s", (res := feautured_models.FeaturedArticle.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := core_models.WorkflowLog.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := core_models.Galley.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := cron_models.CronTask.objects.filter(article=article)).delete()[0], res.model.__name__)

            print("deleted %d from %s", (res := discussion_models.Thread.objects.filter(article=article)).delete()[0], res.model.__name__)

            print("deleted %d from %s", (res := metrics_models.ArticleAccess.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := metrics_models.HistoricArticleAccess.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := metrics_models.ArticleLink.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := metrics_models.BookLink.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := metrics_models.AltMetric.objects.filter(article=article)).delete()[0], res.model.__name__)

#            print("deleted %d from %s", (res := repository_models.Repository.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := repository_models.Preprint.objects.filter(article=article)).delete()[0], res.model.__name__)

#            print("deleted %d from %s", (res := press_models.Press.objects.filter(article=article)).delete()[0], res.model.__name__)


            print("deleted %d from %s", (res := journal_models.PinnedArticle.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := journal_models.FixedPubCheckItems.objects.filter(article=article)).delete()[0], res.model.__name__)
            print("deleted %d from %s", (res := journal_models.PrePublicationChecklistItem.objects.filter(article=article)).delete()[0], res.model.__name__)

