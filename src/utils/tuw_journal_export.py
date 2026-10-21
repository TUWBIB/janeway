# ============================================================================
# HANDOFF NOTE -- journal export/import (round-trip verified, 2026-10-20)
# ============================================================================
# STATUS: DONE
# - tuw_export_journal / tuw_import_journal commands + this module implemented
#   (bundle = journal.json + files/, schema v1).
# - Full round-trip verified on a live DB (same-system import): all
#   journal-scoped counts match the bundle and the source journal is left
#   untouched.
#
# KEY FACTS ABOUT THE DATA MODEL
# - core.File.article / FileHistory.article are PLAIN article_id int columns,
#   not FKs -- the importer remaps them with a two-phase placeholder update
#   RESTRICTED to the pks of files/histories imported in this bundle.
#
# KEY IN-IMPORT DESIGN DECISIONS (all in this file)
# - dict_to_model: the pk is applied via the "pk" key only; the pk column
#   ("id") inside fields is skipped. Setting it as a plain field would put
#   instance.pk on a FRESH (same-system) copy and turn every save() into an
#   UPDATE of the SOURCE row.
# - dict_to_model: names ending in "_id" that are NOT a real FK (plain int
#   columns like File.article_id, generic-FK parts like Task.object_id) are
#   treated as regular fields, resolving a declared fk_remap when present.
# - Shared/global reference data (roles, interests, countries, locations,
#   organizations, organization_names, keywords, news tags, task events) is
#   imported with link_existing=True: on a same-system import the row is
#   linked by pk, on a fresh system it is created with the source pk.
# - ControlledAffiliation: frozen-author-scoped rows are created (they must
#   follow the fresh FrozenAuthor rows); account-scoped rows (frozen_author
#   null) are shared per-account data and are linked by pk when present.
# - The two m2m signals that would duplicate explicitly-imported rows are
#   disconnected for the duration of the import (issue_articles_change ->
#   extra ArticleOrdering; backwards_compat_authors -> extra FrozenAuthor).
# - fk_remaps carry INSTANCES (never ints): pk_map = {old_journal_pk:
#   journal}; an int would raise "must be a <Model> instance" on setattr.
# - The file<->history m2m is restored via files_map (bundle pk -> imported
#   instance), not by comparing bundle pks with imported pks.
#
# REMAINING (optional)
# - Add unit tests (src/utils/tests/test_tuw_journal_export.py) via the django
#   test runner (`make check` runs sqlite).
# ============================================================================

"""
Full journal export/import support.

Implements the logic behind the ``tuw_export_journal`` and
``tuw_import_journal`` management commands.

Bundle layout
=============

::

    <journal_code>-<timestamp>/
        journal.json                     # all data, human readable, no binaries
        files/
            articles/<article_pk>/<path>/<uuid_filename>
                                         # article files (incl. reviews/ subdirs)
            journals/<journal_pk>/<uuid_filename>
                                         # journal-level files
            issues/<issue_pk>/<uuid_filename>
                                         # issue galley files
            profile_images/<uuid>        # account profile images
            media/<path>                 # Django FileField assets (MEDIA_ROOT)

All binary content is stored as plain (unencoded) files; ``journal.json``
references them through the ``binaries`` manifest using the relative path
under ``files/`` as ``rel``.

Design notes
------------
* Pks are preserved on import where possible (``dict_to_model``), so that
  self-referential data (e.g. preprint_journal_article) keeps working.
* Pks embedded in FileField names (``journals/<pk>/...``, ``issues/<pk>/...``,
  ``articles/<pk>/...``) are remapped after the owning object is created.
* django-modeltranslation fields (``title``, ``abstract``, ...) are exported
  as a ``_translations`` block: ``{field: {lang: value}}``.
* Models that are TUW-specific or optional (tuw_sync, metrics) are skipped
  gracefully if they are not installed on a given instance.
"""

import hashlib
import json
import os
import re
import sys
import shutil
import time
import uuid as uuid_lib
from datetime import date, datetime, time as dt_time, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils import timezone

from core import files as core_files
from core import models as core_models
from core.homepage_elements.carousel import models as carousel_models
from cms import models as cms_models
from comms import models as comms_models
from copyediting import models as copyediting_models
from identifiers import models as identifier_models
from journal import models as journal_models
from production import models as production_models
from proofing import models as proofing_models
from press import models as press_models
from review import models as review_models
from submission import models as submission_models
from utils import install as utils_install

SCHEMA_VERSION = 1

# Field names that hold a reference to another record instead of a value
# (handled separately by the importer; excluded from plain field dumps).
_SKIP_FIELDS = {
    "pk": lambda obj: True,
}

# Related names (m2m) we restore per model, mapped to the related model class
# name (resolved lazily to avoid import issues).
M2M_RESTORE = {
    "core.Account": {"interest": "core.Interest"},
    "core.Organization": {"locations": "core.Location"},
    "core.Task": {
        "complete_events": "core.TaskCompleteEvents",
        "assignees": "core.Account",
    },
    "review.ReviewForm": {"elements": "review.ReviewFormElement"},
    "journal.Journal": {"keywords": "submission.Keyword"},
    "core.Workflow": {"elements": "core.WorkflowElement"},
    "core.File": {"history": "core.FileHistory"},
    "submission.Article": {
        "authors": "core.Account",
        "manuscript_files": "core.File",
        "data_figure_files": "core.File",
        "source_files": "core.File",
        "publisher_notes": "submission.PublisherNote",
        "supplementary_files": "core.SupplementaryFile",
    },
    "submission.Section": {
        "editors": "core.Account",
        "section_editors": "core.Account",
    },
    "journal.Issue": {"articles": "submission.Article"},
    "core.Galley": {"images": "core.File"},
    "review.ReviewRound": {"review_files": "core.File"},
    "review.RevisionRequest": {"actions": "review.RevisionAction"},
    "production.TypesetTask": {
        "files_for_typesetting": "core.File",
        "galleys_loaded": "core.File",
    },
    "copyediting.CopyeditAssignment": {
        "files_for_copyediting": "core.File",
        "copyeditor_files": "core.File",
    },
    "copyediting.AuthorReview": {"files_updated": "core.File"},
    "proofing.ProofingTask": {
        "galleys_for_proofing": "core.Galley",
        "proofed_files": "core.File",
        "notes": "proofing.Note",
    },
    "proofing.TypesetterProofingTask": {
        "galleys": "core.Galley",
        "files": "core.File",
    },
    "carousel.Carousel": {
        "articles": "submission.Article",
        "news_articles": "comms.NewsItem",
        "issues": "journal.Issue",
    },
    "comms.NewsItem": {"tags": "comms.Tag"},
}

try:
    from tuw_sync import models as tuw_sync_models

    HAS_TUW_SYNC = True
except Exception:  # pragma: no cover
    HAS_TUW_SYNC = False

try:
    from metrics import models as metrics_models

    HAS_METRICS = True
except Exception:  # pragma: no cover
    HAS_METRICS = False


# ---------------------------------------------------------------------------
# Value (de)serialization
# ---------------------------------------------------------------------------

# Set by import_bundle() to {old_journal_pk: new_journal}. dict_to_model uses
# this to route every FK to the Journal model at the imported journal, so the
# whole bundle is anchored to the new journal (and never to the source one).
_IMPORT_JOURNAL_REMAP = None
_IMPORT_JOURNAL_MODEL = None


def _jsonable(value):
    """Recursively converts a value into JSON-safe structures."""
    if isinstance(value, (dict,)):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (date, dt_time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (uuid_lib.UUID, bytes, bytearray)):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def parse_datetime(value):
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = timezone.make_aware(parsed)
    return parsed


def parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def parse_time(value):
    if not value:
        return None
    return dt_time.fromisoformat(value)


def _coerce(field, value):
    """Coerce a JSON value to the type expected by ``field``."""
    if value is None:
        return None
    if isinstance(field, models.FileField):
        return value if value else None
    if isinstance(field, models.DateTimeField):
        return parse_datetime(value)
    if isinstance(field, models.DateField):
        return parse_date(value)
    if isinstance(field, models.TimeField):
        return parse_time(value)
    if isinstance(field, models.UUIDField):
        return uuid_lib.UUID(value)
    return value


def _concrete_field_names(model):
    return [
        f.name
        for f in model._meta.get_fields()
        if f.concrete and not f.many_to_many
    ]


def _fk_fields(model):
    # isinstance covers ForeignKey and its OneToOneField subclass, while
    # skipping reverse relations and GenericForeignKey (no internal type).
    result = {}
    for f in model._meta.get_fields():
        if isinstance(f, models.ForeignKey):
            result[f.name] = f
    return result


def _m2m_fields(model):
    return {
        f.name: f
        for f in model._meta.get_fields()
        if f.many_to_many and not f.auto_created
    }


def _translatable_fields(model):
    try:
        from modeltranslation import registry

        opts = registry.get_options(model)
        if opts is not None and getattr(opts, "fields", None):
            return list(opts.fields)
    except Exception:
        pass
    return []


def _language_codes():
    return [code for code, _label in getattr(settings, "LANGUAGES", [])]


def model_to_dict(obj):
    """Serialize a model instance.

    Concrete fields are stored under their normal names. FK fields are
    stored as ``<name>_id`` integers (the object entry is dropped),
    declared m2m fields are stored as lists of related pks, and
    modeltranslation fields go into a ``_translations`` block.
    """
    model = type(obj)
    data = {}
    for name in _concrete_field_names(model):
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        data[name] = _jsonable(value)

    for name in _fk_fields(model):
        try:
            data.pop(name, None)
            data["{}_id".format(name)] = getattr(obj, "{}_id".format(name), None)
        except Exception:
            continue

    for name in _m2m_fields(model):
        try:
            related_pks = list(getattr(obj, name).values_list("pk", flat=True))
        except Exception:
            try:
                related_pks = [rel.pk for rel in getattr(obj, name).all()]
            except Exception:
                related_pks = []
        data[name] = [p for p in related_pks if p is not None]

    translatable = _translatable_fields(model)
    if translatable:
        translations = {}
        for field_name in translatable:
            langs = {}
            for lang in _language_codes():
                attr = "{}_{}".format(field_name, lang)
                if hasattr(obj, attr):
                    try:
                        value = getattr(obj, attr)
                    except Exception:
                        value = None
                    if value not in (None, ""):
                        langs[lang] = _jsonable(value)
            if langs:
                translations[field_name] = langs
        if translations:
            data["_translations"] = translations
    return data


def dict_to_model(model, values, fk_remap=None, **extra):
    """Create (or update, when ``pk`` is present) an instance from a dump.

    Foreign keys referenced by ``<field>_id`` are resolved; ``fk_remap``
    may map ``(old_pk) -> instance`` per field to resolve references that
    point at records created earlier in the same import. Unknown
    references are left unset so that a missing related record never
    blocks the whole import.
    """
    values = {k: v for k, v in values.items() if not k.startswith("_")}
    fk_map = _fk_fields(model)
    m2m_names = set(_m2m_fields(model))

    kwargs = {}
    pk_field_name = model._meta.pk.name
    for name, value in values.items():
        if name == "pk":
            kwargs["pk"] = value
            continue
        if name == pk_field_name:
            # The exported bundle carries the pk column (usually "id") inside
            # fields as well. Applying it would setattr(instance, "id", pk),
            # which sets instance.pk and turns every save() into an UPDATE of
            # the SOURCE row on a same-system import. The pk is handled via
            # the "pk" key only.
            continue
        if name in m2m_names:
            continue  # m2ms are restored separately
        if name in fk_map:
            continue  # real FK field names are handled in the FK loop below
        if name.endswith("_id"):
            base = name[:-3]
            if base in fk_map:
                # attname of a real FK (e.g. owner_id); the FK loop handles it
                continue
            # A plain *_id column (e.g. core.File.article_id) or a generic-FK
            # part (e.g. core.Task.object_id). Resolve it through a declared
            # fk_remap (keyed by the full column name) when one is provided,
            # otherwise keep the raw value -- the importer fixes plain
            # article_id columns with its two-phase remap later.
            remap = fk_remap.get(name) if fk_remap is not None else None
            resolved = None
            if remap is not None:
                if callable(remap):
                    try:
                        resolved = remap(value)
                    except Exception:
                        resolved = None
                elif isinstance(remap, dict):
                    resolved = remap.get(value)
                # remap is None -> explicitly left unresolved
            if resolved is not None:
                kwargs[name] = resolved.pk if hasattr(resolved, "pk") else resolved
            else:
                try:
                    field = model._meta.get_field(name)
                    kwargs[name] = _coerce(field, value)
                except Exception:
                    pass
            continue
        try:
            field = model._meta.get_field(name)
        except Exception:
            continue
        if field.many_to_many:
            continue
        kwargs[name] = _coerce(field, value)

    fk_pending = {}
    for name, field in fk_map.items():
        ref = values.get("{}_id".format(name))
        if ref in (None, ""):
            continue
        related_model = field.related_model
        related = None
        if (
            _IMPORT_JOURNAL_REMAP is not None
            and _IMPORT_JOURNAL_MODEL is not None
            and field.related_model is _IMPORT_JOURNAL_MODEL
        ):
            # route every FK to the journal at the imported journal
            # (the remap values are Journal INSTANCES; an int here would make
            # the FK assignment below raise TypeError)
            related = _IMPORT_JOURNAL_REMAP.get(ref)
        elif fk_remap is not None and name in fk_remap:
            # a remap is declared for this field: never fall back to the
            # database, where the old pk may belong to an unrelated row
            remap = fk_remap[name]
            if callable(remap):
                try:
                    related = remap(ref)
                except Exception:
                    related = None
            elif isinstance(remap, dict):
                related = remap.get(ref)
        else:
            try:
                related = related_model.objects.get(pk=int(ref))
            except (related_model.DoesNotExist, ValueError, TypeError):
                related = None
        if related is not None:
            kwargs[name] = related
        else:
            # remember it; it may be resolvable in a later pass
            fk_pending[name] = ref

    kwargs.update(extra)

    # Preserve the source pk when the row does not already exist (fresh
    # system) so self-referential data keeps working. If the row DOES already
    # exist (importing into the same system as the source), never overwrite
    # it -- create a fresh copy so the source journal is left untouched.
    pk = values.get("pk")
    instance = None
    if pk is not None:
        try:
            model.objects.get(pk=pk)
            instance = model()  # same-system: don't clobber the source row
        except (model.DoesNotExist, ValueError):
            instance = model(pk=pk)  # fresh system: preserve the pk
    else:
        instance = model()

    for name, value in kwargs.items():
        if name == "pk":
            continue
        setattr(instance, name, value)

    if fk_pending:
        instance._pending_fk_refs = dict(fk_pending)
    return instance


def apply_translations(instance, values):
    """Apply a ``_translations`` block to an instance."""
    translations = values.get("_translations") or {}
    for field_name, langs in translations.items():
        for lang, value in langs.items():
            attr = "{}_{}".format(field_name, lang)
            if hasattr(instance, attr):
                try:
                    setattr(instance, attr, value)
                except Exception:
                    pass


def _restore_m2m(instance, values, pk_remap=None):
    model_key = "{}.{}".format(
        type(instance)._meta.app_label, type(instance).__name__
    )
    restore_map = M2M_RESTORE.get(model_key, {})
    for m2m_name, related_label in restore_map.items():
        pks = values.get(m2m_name)
        if not pks:
            continue
        related_model = _resolve_model(related_label)
        if related_model is None:
            continue
        remapped = pks
        if pk_remap is not None:
            mapping = pk_remap.get(related_label)
            if mapping is not None:
                remapped = _pks(pks, mapping)
        try:
            related = related_model.objects.filter(pk__in=remapped)
            getattr(instance, m2m_name).set(related)
        except Exception:
            pass


def _resolve_model(label):
    app_label, model_name = label.split(".")
    try:
        from django.apps import apps

        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def resolve_pending_fks(instance, fk_remap, log=None):
    """Resolve FKs that could not be resolved when the instance was built.

    ``fk_remap`` maps field name -> {old_pk: instance} (or ``None`` to mark
    the field as intentionally unresolved, or a callable ``old_pk -> obj``).
    Fields without a remap entry are looked up in the database.
    """
    pending = getattr(instance, "_pending_fk_refs", None)
    if not pending:
        return
    fk_map = _fk_fields(type(instance))
    for name, ref in pending.items():
        field = fk_map.get(name)
        if field is None:
            continue
        remap = fk_remap.get(name)
        related = None
        if callable(remap):
            try:
                related = remap(ref)
            except Exception:
                related = None
        elif isinstance(remap, dict):
            related = remap.get(ref)
        elif remap is None:
            related = None  # explicitly unresolved
        else:
            try:
                related = field.related_model.objects.get(pk=int(ref))
            except (field.related_model.DoesNotExist, ValueError, TypeError):
                related = None
        if related is not None:
            setattr(instance, name, related)
        elif remap is None:
            pass  # intentionally left unresolved
        elif log:
            log(
                "  warning: unresolved {} -> {} pk {}".format(
                    type(instance).__name__, name, ref
                )
            )
    try:
        del instance._pending_fk_refs
    except AttributeError:
        pass


def _save(instance, extra=None, pk_remap=None, log=None, fk_remap=None):
    """Save an instance, applying translations and m2ms first."""
    apply_translations(instance, extra or {})
    resolve_pending_fks(instance, fk_remap or {}, log)
    instance.save()
    _restore_m2m(instance, extra or {}, pk_remap)
    return instance


# ---------------------------------------------------------------------------
# Binary file handling
# ---------------------------------------------------------------------------


def _media_root():
    return settings.MEDIA_ROOT


def _base_files_dir():
    return os.path.join(settings.BASE_DIR, "files")


def _file_name(value):
    """Return the stored FileField name from a FieldFile/str/None."""
    if not value:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "name", None)


def _pks(refs, mapping=None):
    """Convert a list of source pks to target pks via ``mapping`` (old->obj).

    Instances are reduced to their (possibly new) pk; raw ints pass through.
    """
    out = []
    for ref in refs:
        obj = mapping.get(ref) if mapping is not None else ref
        out.append(obj.pk if hasattr(obj, "pk") else obj)
    return out


def _copy_to_bundle(src, rel, files_root):
    """Copy ``src`` (absolute path) into the bundle files dir. Returns rel or
    None when the source does not exist."""
    if not src or not os.path.isfile(src):
        return None
    dest = os.path.join(files_root, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    return rel


def _copy_from_bundle(rel, files_root, dest):
    """Copy a file out of the bundle. Returns True on success."""
    src = os.path.join(files_root, rel)
    if not os.path.isfile(src):
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    return True


# ---------------------------------------------------------------------------
# EXPORT
# ---------------------------------------------------------------------------


# Progress verbosity for _dump_model(): set by export_bundle() so every dump
# section (accounts, files, articles, the "remaining sections" block, ...)
# reports progress without having to pass verbose through 60+ call sites.
_EXPORT_VERBOSE = False


def _dump_model(data, key, queryset, extra_fn=None, verbose=None):
    """Dump a queryset into ``data[key]`` as a list of {pk, fields}."""
    if verbose is None:
        verbose = _EXPORT_VERBOSE
    try:
        total = queryset.count()
    except Exception:
        total = 0
    rows = []
    last_beat = 0.0
    for obj in queryset:
        row = {"pk": obj.pk, "fields": model_to_dict(obj)}
        if extra_fn:
            extra_fn(obj, row)
        rows.append(row)
        if verbose and total and len(rows) % 100 == 0:
            now = time.monotonic()
            if now - last_beat >= 2.0:
                last_beat = now
                print("    {}: {}/{} ...".format(key, len(rows), total))
                sys.stdout.flush()
    data[key] = rows
    if verbose:
        # always log (even empty sections) so long exports never look stuck
        print("  dumped {}: {}".format(key, len(rows)))
        sys.stdout.flush()
    return rows


def _dump_settings(data, journal):
    rows = []
    for setting_value in core_models.SettingValue.objects.filter(
        journal=journal
    ).select_related("setting", "setting__group"):
        setting = setting_value.setting
        entry = {
            "group": setting.group.name,
            "name": setting.name,
            "value": setting_value.value,
        }
        translations = {}
        for lang in _language_codes():
            attr = "value_{}".format(lang)
            if hasattr(setting_value, attr):
                try:
                    value = getattr(setting_value, attr)
                except Exception:
                    value = None
                if value not in (None, ""):
                    translations[lang] = value
        if translations:
            entry["_translations"] = translations
        rows.append(entry)
    data["settings"] = rows
    return rows


def export_bundle(
    journal, output_dir, include_binaries=True, verbose=True,
    include_article_access=True,
):
    """Export ``journal`` (a journal_models.Journal) into a bundle directory.

    ``include_article_access=False`` skips the (potentially very large)
    article access metrics: the per-event ``ArticleAccess`` log and the
    ``HistoricArticleAccess`` COUNTER aggregates.

    Returns a summary dict with counts.
    """

    def log(msg):
        if verbose:
            print(msg)
            sys.stdout.flush()

    bundle_dir = os.path.join(output_dir, "{}-{}".format(
        journal.code, timezone.now().strftime("%Y%m%d-%H%M%S")
    ))
    files_root = os.path.join(bundle_dir, "files")
    os.makedirs(files_root, exist_ok=True)

    log("Exporting journal '{}' (pk {}) to {}".format(journal.code, journal.pk, bundle_dir))

    global _EXPORT_VERBOSE
    _EXPORT_VERBOSE = verbose

    data = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": timezone.now().isoformat(),
        "journal_pk": journal.pk,
        "binaries": [],
    }

    binaries = data["binaries"]
    # One detail line per referenced binary that is missing on disk;
    # reported in the final warning so the operator can locate each file.
    bin_missing = []

    # ---- accounts (everyone referenced by the journal) -------------------
    account_pks = set()

    def collect_account(pk):
        if pk:
            account_pks.add(pk)

    log("  collecting referenced accounts ...")
    articles = submission_models.Article.objects.filter(journal=journal)
    article_pks = list(articles.values_list("pk", flat=True))
    issues = journal_models.Issue.objects.filter(journal=journal)
    issue_pks = list(issues.values_list("pk", flat=True))

    for obj in articles.select_related("owner", "correspondence_author"):
        collect_account(obj.owner_id)
        collect_account(obj.correspondence_author_id)
    for obj in issues:
        for account in obj.editors.all():
            collect_account(account.pk)
    for row in journal_models.IssueEditor.objects.filter(issue__journal=journal):
        collect_account(row.account_id)
    for row in submission_models.FrozenAuthor.objects.filter(article__journal=journal):
        collect_account(row.author_id)
    for row in review_models.ReviewAssignment.objects.filter(article__journal=journal):
        collect_account(row.reviewer_id)
        collect_account(row.editor_id)
    for row in review_models.EditorAssignment.objects.filter(article__journal=journal):
        collect_account(row.editor_id)
    for row in review_models.ReviewerRating.objects.filter(
        assignment__article__journal=journal
    ):
        collect_account(row.rater_id)
    for row in copyediting_models.CopyeditAssignment.objects.filter(
        article__journal=journal
    ):
        collect_account(row.copyeditor_id)
        collect_account(row.editor_id)
    for row in production_models.ProductionAssignment.objects.filter(
        article__journal=journal
    ):
        collect_account(row.production_manager_id)
        collect_account(row.editor_id)
    for row in production_models.TypesetTask.objects.filter(
        assignment__article__journal=journal
    ):
        collect_account(row.typesetter_id)
    for row in proofing_models.ProofingAssignment.objects.filter(
        article__journal=journal
    ):
        collect_account(row.proofing_manager_id)
        collect_account(row.editor_id)
    for row in proofing_models.ProofingTask.objects.filter(
        round__assignment__article__journal=journal
    ):
        collect_account(row.proofreader_id)
    for row in proofing_models.TypesetterProofingTask.objects.filter(
        proofing_task__round__assignment__article__journal=journal
    ):
        collect_account(row.typesetter_id)
    for row in core_models.AccountRole.objects.filter(journal=journal):
        collect_account(row.user_id)
    for row in core_models.EditorialGroupMember.objects.filter(
        group__journal=journal
    ):
        collect_account(row.user_id)
    for row in submission_models.Note.objects.filter(article__journal=journal):
        collect_account(row.creator_id)
    for row in core_models.WorkflowLog.objects.filter(article__journal=journal):
        collect_account(row.user_id)
    for row in core_models.Task.objects.filter(
        content_type__model="article", object_id__in=article_pks
    ):
        for account in row.assignees.all():
            collect_account(account.pk)
        collect_account(row.completed_by_id)
    for row in comms_models.NewsItem.objects.filter(
        content_type__model="journal", object_id=journal.pk
    ):
        collect_account(row.posted_by_id)
    for row in journal_models.Notifications.objects.filter(journal=journal):
        collect_account(row.user_id)
    for row in core_models.AccessRequest.objects.filter(journal=journal):
        collect_account(row.user_id)
    for row in review_models.DecisionDraft.objects.filter(article__journal=journal):
        collect_account(row.editor_id)
        collect_account(row.section_editor_id)
    for row in copyediting_models.AuthorReview.objects.filter(
        assignment__article__journal=journal
    ):
        collect_account(row.author_id)
    for section in submission_models.Section.objects.filter(journal=journal):
        for account in section.editors.all():
            collect_account(account.pk)
        for account in section.section_editors.all():
            collect_account(account.pk)

    # file owners must be collected up front so the accounts dump below
    # includes accounts referenced only as file/file-history owners
    # (e.g. a system account that uploaded journal-level files)
    file_queryset = core_models.File.objects.filter(article_id__in=article_pks)
    # issue galley files (stored in files/issues/<issue_pk>/)
    file_queryset = file_queryset | core_models.File.objects.filter(
        issuegalley__issue__journal=journal
    )
    # journal-level files: match files on disk in files/journals/<pk>
    journal_file_dir = os.path.join(_base_files_dir(), "journals", str(journal.pk))
    journal_file_uuids = []
    if os.path.isdir(journal_file_dir):
        journal_file_uuids = [
            name
            for name in os.listdir(journal_file_dir)
            if os.path.isfile(os.path.join(journal_file_dir, name))
        ]
    if journal_file_uuids:
        file_queryset = file_queryset | core_models.File.objects.filter(
            article_id__isnull=True, uuid_filename__in=journal_file_uuids
        )
    for pk in file_queryset.values_list("owner_id", flat=True):
        collect_account(pk)
    file_history_qs = core_models.FileHistory.objects.filter(
        models.Q(article_id__in=article_pks) | models.Q(file__in=file_queryset)
    )
    for pk in file_history_qs.values_list("owner_id", flat=True):
        collect_account(pk)
    for pk in submission_models.PublisherNote.objects.filter(
        publisher_notes__journal=journal
    ).values_list("creator_id", flat=True):
        collect_account(pk)

    log("  collected {} referenced accounts".format(len(account_pks)))
    accounts = core_models.Account.objects.filter(pk__in=sorted(account_pks))
    _dump_model(data, "accounts", accounts)
    log("  exporting journal data ...")

    # interests + roles referenced by the accounts above (shared reference data)
    interest_pks = set()
    for row in core_models.Account.objects.filter(pk__in=account_pks):
        interest_pks.update(row.interest.values_list("pk", flat=True))
    _dump_model(
        data,
        "interests",
        core_models.Interest.objects.filter(pk__in=sorted(interest_pks)),
    )
    role_pks = set()
    for row in core_models.AccountRole.objects.filter(journal=journal):
        role_pks.add(row.role_id)
    for row in core_models.AccessRequest.objects.filter(journal=journal):
        role_pks.add(row.role_id)
    _dump_model(
        data,
        "roles",
        core_models.Role.objects.filter(pk__in=sorted(role_pks)),
    )

    # task completion events referenced by the journal's tasks
    task_qs = core_models.Task.objects.filter(
        content_type__model="article", object_id__in=article_pks
    )
    task_event_pks = set()
    for task in task_qs:
        task_event_pks.update(task.complete_events.values_list("pk", flat=True))
    _dump_model(
        data,
        "task_events",
        core_models.TaskCompleteEvents.objects.filter(pk__in=sorted(task_event_pks)),
    )

    # content types referenced by generic FKs (pks can differ between installs)
    ct_pks = set()
    ct_pks.add(ContentType.objects.get_for_model(journal).pk)
    ct_pks.add(ContentType.objects.get_for_model(submission_models.Article).pk)
    for row in core_models.HomepageElement.objects.filter(
        content_type__app_label="journal"
    ):
        ct_pks.add(row.content_type_id)
    for row in core_models.Contacts.objects.filter(content_type__app_label="journal"):
        ct_pks.add(row.content_type_id)
    for row in core_models.Task.objects.filter(
        content_type__model="article", object_id__in=article_pks
    ):
        ct_pks.add(row.content_type_id)
    for row in comms_models.NewsItem.objects.filter(
        content_type__model="journal", object_id=journal.pk
    ):
        ct_pks.add(row.content_type_id)
    _dump_model(
        data,
        "content_types",
        ContentType.objects.filter(pk__in=sorted(p for p in ct_pks if p)),
    )

    # profile images
    if include_binaries:
        for account in accounts:
            if account.profile_image:
                name = account.profile_image.name
                src = os.path.join(_media_root(), name)
                rel = _copy_to_bundle(src, os.path.join("profile_images", os.path.basename(name)), files_root)
                if rel:
                    binaries.append(
                        {"rel": rel, "kind": "profile_image", "account_id": account.pk}
                    )
                elif include_binaries:
                    bin_missing.append(
                        "profile image of account {} ({}): {}".format(
                            account.pk, account.username, src
                        )
                    )

    # ---- journal-level users/roles ---------------------------------------
    _dump_model(
        data,
        "account_roles",
        core_models.AccountRole.objects.filter(journal=journal),
    )
    _dump_model(
        data,
        "editorial_groups",
        core_models.EditorialGroup.objects.filter(journal=journal),
    )
    _dump_model(
        data,
        "editorial_group_members",
        core_models.EditorialGroupMember.objects.filter(group__journal=journal),
    )

    # ---- affiliations / organizations ------------------------------------
    def _org_for_affiliation(affiliation):
        org = getattr(affiliation, "organization", None)
        return org

    orgs = set()
    for affiliation in core_models.ControlledAffiliation.objects.filter(
        models.Q(account__pk__in=account_pks)
        | models.Q(frozen_author__article__journal=journal)
    ):
        if affiliation.organization_id:
            orgs.add(affiliation.organization_id)

    countries = set()
    if orgs:
        for location in core_models.Location.objects.filter(
            organization__pk__in=orgs
        ):
            if location.country_id:
                countries.add(location.country_id)

    _dump_model(
        data,
        "countries",
        core_models.Country.objects.filter(pk__in=sorted(countries)),
    )
    _dump_model(
        data,
        "locations",
        core_models.Location.objects.filter(organization__pk__in=orgs),
    )
    _dump_model(
        data,
        "organizations",
        core_models.Organization.objects.filter(pk__in=sorted(orgs)),
    )

    org_qs = core_models.Organization.objects.filter(pk__in=orgs) if orgs else (
        core_models.Organization.objects.none()
    )
    _dump_model(data, "organization_names", core_models.OrganizationName.objects.filter(
        models.Q(ror_display_for__in=org_qs)
        | models.Q(label_for__in=org_qs)
        | models.Q(custom_label_for__in=org_qs)
        | models.Q(alias_for__in=org_qs)
        | models.Q(acronym_for__in=org_qs)
    ))

    # ---- journal core ------------------------------------------------------
    journal_row = {"pk": journal.pk, "fields": model_to_dict(journal)}
    data["journal"] = journal_row

    # journal image fields: dump the stored FileField names as binaries
    if include_binaries:
        for field_name in (
            "press_image_override",
            "default_cover_image",
            "default_large_image",
            "header_image",
            "favicon",
            "default_profile_image",
            "under_construction_image",
        ):
            name = _file_name(getattr(journal, field_name, None))
            if name:
                src = os.path.join(_media_root(), name)
                rel = _copy_to_bundle(src, os.path.join("media", name), files_root)
                if rel:
                    binaries.append(
                        {
                            "rel": rel,
                            "kind": "media",
                            "target": "journal.{}".format(field_name),
                        }
                    )
                elif include_binaries:
                    bin_missing.append(
                        "journal.{} ({}): {}".format(field_name, journal.code, src)
                    )

    _dump_settings(data, journal)

    # ---- XSL files ---------------------------------------------------------
    _dump_model(
        data,
        "xsl_files",
        core_models.XSLFile.objects.filter(journal=journal),
    )
    if include_binaries:
        for xsl in core_models.XSLFile.objects.filter(journal=journal):
            src = os.path.join(_base_files_dir(), "xsl", xsl.file.name)
            rel = _copy_to_bundle(src, os.path.join("xsl", xsl.file.name), files_root)
            if rel:
                binaries.append(
                    {
                        "rel": rel,
                        "kind": "xsl",
                        "target": "xsl.{}".format(xsl.pk),
                        "name": xsl.file.name,
                    }
                )
            elif include_binaries:
                bin_missing.append(
                    "xsl file '{}' (XSLFile pk {}): {}".format(
                        xsl.file.name, xsl.pk, src
                    )
                )

    # ---- sections / licenses / issue types / submission config ------------
    _dump_model(
        data, "sections", submission_models.Section.objects.filter(journal=journal)
    )
    _dump_model(
        data, "licenses", submission_models.Licence.objects.filter(journal=journal)
    )
    _dump_model(
        data, "issue_types", journal_models.IssueType.objects.filter(journal=journal)
    )
    _dump_model(
        data,
        "submission_items",
        cms_models.SubmissionItem.objects.filter(journal=journal),
    )
    _dump_model(
        data,
        "fields_custom",
        submission_models.Field.objects.filter(journal=journal),
    )

    sub_config = submission_models.SubmissionConfiguration.objects.filter(
        journal=journal
    ).first()
    if sub_config:
        data["submission_config"] = {
            "pk": sub_config.pk,
            "fields": model_to_dict(sub_config),
        }

    # ---- review forms ------------------------------------------------------
    _dump_model(
        data,
        "review_forms",
        review_models.ReviewForm.objects.filter(journal=journal),
    )
    form_pks = list(
        review_models.ReviewForm.objects.filter(journal=journal).values_list(
            "pk", flat=True
        )
    )
    _dump_model(
        data,
        "review_form_elements",
        review_models.ReviewFormElement.objects.filter(reviewform__pk__in=form_pks),
    )

    # ---- workflow ----------------------------------------------------------
    workflow = core_models.Workflow.objects.filter(journal=journal).first()
    if workflow:
        data["workflow"] = {
            "pk": workflow.pk,
            "fields": model_to_dict(workflow),
            "elements": [
                element.pk
                for element in workflow.elements.all()
            ],
        }
    _dump_model(
        data,
        "workflow_elements",
        core_models.WorkflowElement.objects.filter(journal=journal),
    )

    # ---- misc journal-level models ----------------------------------------
    _dump_model(
        data,
        "domain_aliases",
        core_models.DomainAlias.objects.filter(journal=journal),
    )
    _dump_model(
        data,
        "access_requests",
        core_models.AccessRequest.objects.filter(journal=journal),
    )
    _dump_model(
        data,
        "notifications",
        journal_models.Notifications.objects.filter(journal=journal),
    )
    _dump_model(
        data,
        "preset_pub_check_items",
        journal_models.PresetPublicationCheckItem.objects.filter(journal=journal),
    )

    journal_ct = ContentType.objects.get_for_model(journal)
    _dump_model(
        data,
        "contacts",
        core_models.Contacts.objects.filter(
            content_type=journal_ct, object_id=journal.pk
        ),
    )
    _dump_model(
        data,
        "homepage_elements",
        core_models.HomepageElement.objects.filter(
            content_type=journal_ct, object_id=journal.pk
        ),
    )

    # ---- news / carousel ---------------------------------------------------
    _dump_model(
        data,
        "news",
        comms_models.NewsItem.objects.filter(
            content_type=journal_ct, object_id=journal.pk
        ),
    )
    news_pks = list(
        comms_models.NewsItem.objects.filter(
            content_type=journal_ct, object_id=journal.pk
        ).values_list("pk", flat=True)
    )
    _dump_model(
        data,
        "news_tags",
        comms_models.Tag.objects.filter(tags__pk__in=news_pks)
        if news_pks
        else comms_models.Tag.objects.none(),
    )

    carousel_obj = getattr(journal, "carousel", None)
    if carousel_obj:
        data["carousel"] = {
            "pk": carousel_obj.pk,
            "fields": model_to_dict(carousel_obj),
        }

    _dump_model(
        data,
        "cms_pages",
        cms_models.Page.objects.filter(
            content_type=journal_ct, object_id=journal.pk
        ),
    )
    _dump_model(
        data,
        "cms_navigation_items",
        cms_models.NavigationItem.objects.filter(
            content_type=journal_ct, object_id=journal.pk
        ),
    )

    # ---- keywords / publisher notes ---------------------------------------
    keyword_pks = set()
    keyword_pks.update(
        journal.keywords.values_list("pk", flat=True)
    )
    keyword_pks.update(
        submission_models.KeywordArticle.objects.filter(
            article__journal=journal
        ).values_list("keyword_id", flat=True)
    )
    _dump_model(
        data,
        "keywords",
        submission_models.Keyword.objects.filter(pk__in=sorted(keyword_pks)),
    )
    _dump_model(
        data,
        "keyword_articles",
        submission_models.KeywordArticle.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "publisher_notes",
        submission_models.PublisherNote.objects.filter(
            publisher_notes__journal=journal
        ),
    )

    # ---- files -------------------------------------------------------------
    # (file_queryset was already computed above for the account collection)
    log("  exporting files ...")
    files_by_pk = {}
    _dump_model(
        data,
        "files",
        file_queryset.order_by("pk"),
        extra_fn=lambda f, row: files_by_pk.update({f.pk: f}),
    )

    # journal image FKs that point at core.File records
    for field_name in ("thumbnail_image",):
        value = getattr(journal, "{}_id".format(field_name), None)
        if value and value not in files_by_pk:
            extra = core_models.File.objects.filter(pk=value).first()
            if extra:
                files_by_pk[extra.pk] = extra
                data["files"].append(
                    {"pk": extra.pk, "fields": model_to_dict(extra)}
                )

    # cms media files (media/journals/<pk>/...) are not core.File records
    cms_media_files = cms_models.MediaFile.objects.filter(journal=journal)
    _dump_model(data, "cms_media_files", cms_media_files)

    if include_binaries:
        log("  copying binary files ...")
        _bin_total = 0
        for media_file in cms_media_files:
            if media_file.file:
                name = media_file.file.name
                src = os.path.join(_media_root(), name)
                rel = _copy_to_bundle(
                    src, os.path.join("media", name), files_root
                )
                if rel:
                    binaries.append(
                        {
                            "rel": rel,
                            "kind": "cms_media",
                            "media_file_id": media_file.pk,
                            "name": name,
                        }
                    )
                else:
                    bin_missing.append(
                        "cms media file '{}' (MediaFile pk {}): {}".format(
                            name, media_file.pk, src
                        )
                    )
        for file in files_by_pk.values():
            if file.is_remote:
                continue
            if file.article_id:
                src = os.path.join(
                    _base_files_dir(),
                    "articles",
                    str(file.article_id),
                    file.uuid_filename,
                )
                rel = _copy_to_bundle(
                    src,
                    "articles/{}/{}".format(file.article_id, file.uuid_filename),
                    files_root,
                )
                if rel:
                    binaries.append(
                        {
                            "rel": rel,
                            "kind": "article_file",
                            "file_id": file.pk,
                            "article_id": file.article_id,
                        }
                    )
                    _bin_total += 1
                    if verbose and _bin_total % 25 == 0:
                        log("    {} binary files copied".format(_bin_total))
                else:
                    bin_missing.append(
                        "article file {} (File pk {}, article {}): {}".format(
                            file.uuid_filename, file.pk, file.article_id, src
                        )
                    )
            else:
                src = os.path.join(
                    _base_files_dir(), "journals", str(journal.pk), file.uuid_filename
                )
                rel = _copy_to_bundle(
                    src,
                    "journals/{}/{}".format(journal.pk, file.uuid_filename),
                    files_root,
                )
                if rel:
                    binaries.append(
                        {
                            "rel": rel,
                            "kind": "journal_file",
                            "file_id": file.pk,
                            "journal_id": journal.pk,
                        }
                    )
                    _bin_total += 1
                    if verbose and _bin_total % 25 == 0:
                        log("    {} binary files copied".format(_bin_total))
                else:
                    bin_missing.append(
                        "journal file {} (File pk {}): {}".format(
                            file.uuid_filename, file.pk, src
                        )
                    )
            # extra copies living in article subfolders (review attachments etc.)
            article_dir = os.path.join(_base_files_dir(), "articles", str(file.article_id)) if file.article_id else None
            if article_dir and os.path.isdir(article_dir):
                for dirpath, _dirnames, filenames in os.walk(article_dir):
                    subpath = os.path.relpath(dirpath, article_dir)
                    if subpath == ".":
                        continue  # the primary copy is handled above
                    for filename in filenames:
                        if filename == file.uuid_filename:
                            full_src = os.path.join(dirpath, filename)
                            rel_base = "articles/{}/{}".format(
                                file.article_id, subpath.replace(os.sep, "/")
                            ) + "/" + filename
                            rel = _copy_to_bundle(full_src, rel_base, files_root)
                            if rel:
                                _bin_total += 1
                                if verbose and _bin_total % 25 == 0:
                                    log("    {} binary files copied".format(_bin_total))
                                binaries.append(
                                    {
                                        "rel": rel,
                                        "kind": "article_file_sub",
                                        "file_id": file.pk,
                                        "article_id": file.article_id,
                                        "subpath": subpath.replace(os.sep, "/")
                                        if subpath != "."
                                        else "",
                                    }
                                )
                            else:
                                bin_missing.append(
                                    "article file {} in subfolder {} "
                                    "(File pk {}): {}".format(
                                        file.uuid_filename, subpath, file.pk, full_src
                                    )
                                )

    _dump_model(data, "file_histories", file_history_qs)

    # ---- galleys / supplementary files -------------------------------------
    _dump_model(
        data,
        "galleys",
        core_models.Galley.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "supplementary_files",
        core_models.SupplementaryFile.objects.filter(
            file__article_id__in=article_pks
        ),
    )

    # ---- issues ------------------------------------------------------------
    def _issue_extra(issue, row):
        nonlocal bin_missing
        if include_binaries:
            if issue.large_image:
                src = os.path.join(_media_root(), issue.large_image.name)
                rel = _copy_to_bundle(
                    src, os.path.join("media", issue.large_image.name), files_root
                )
                if rel:
                    binaries.append(
                        {
                            "rel": rel,
                            "kind": "media",
                            "target": "issue.large_image",
                            "issue_id": issue.pk,
                        }
                    )
                else:
                    bin_missing.append(
                        "issue {} large_image: {}".format(issue.pk, src)
                    )
            if issue.cover_image:
                src = os.path.join(_media_root(), issue.cover_image.name)
                rel = _copy_to_bundle(
                    src, os.path.join("media", issue.cover_image.name), files_root
                )
                if rel:
                    binaries.append(
                        {
                            "rel": rel,
                            "kind": "media",
                            "target": "issue.cover_image",
                            "issue_id": issue.pk,
                        }
                    )
                else:
                    bin_missing.append(
                        "issue {} cover_image: {}".format(issue.pk, src)
                    )

    log("  exporting issues ...")
    _dump_model(data, "issues", issues, extra_fn=_issue_extra)
    _dump_model(
        data,
        "issue_editors",
        journal_models.IssueEditor.objects.filter(issue__journal=journal),
    )
    _dump_model(
        data,
        "section_ordering",
        journal_models.SectionOrdering.objects.filter(issue__journal=journal),
    )
    _dump_model(
        data,
        "article_ordering",
        journal_models.ArticleOrdering.objects.filter(issue__journal=journal),
    )
    _dump_model(
        data,
        "pinned_articles",
        journal_models.PinnedArticle.objects.filter(journal=journal),
    )

    def _issue_galley_extra(galley, row):
        nonlocal bin_missing
        if include_binaries and galley.file:
            src = os.path.join(
                _base_files_dir(), "issues", str(galley.issue_id), galley.file.uuid_filename
            )
            rel = _copy_to_bundle(
                src,
                "issues/{}/{}".format(galley.issue_id, galley.file.uuid_filename),
                files_root,
            )
            if rel:
                binaries.append(
                    {
                        "rel": rel,
                        "kind": "issue_galley_file",
                        "issue_id": galley.issue_id,
                        "file_id": galley.file_id,
                    }
                )
            else:
                bin_missing.append(
                    "issue galley file (IssueGalley pk {}, issue {}): {}".format(
                        galley.pk, galley.issue_id, src
                    )
                )

    _dump_model(
        data,
        "issue_galleys",
        journal_models.IssueGalley.objects.filter(issue__journal=journal),
        extra_fn=_issue_galley_extra,
    )

    # ---- articles ----------------------------------------------------------
    def _article_extra(article, row):
        nonlocal bin_missing
        if include_binaries and article.meta_image:
            src = os.path.join(_media_root(), article.meta_image.name)
            rel = _copy_to_bundle(
                src, os.path.join("media", article.meta_image.name), files_root
            )
            if rel:
                binaries.append(
                    {
                        "rel": rel,
                        "kind": "media",
                        "target": "article.meta_image",
                        "article_id": article.pk,
                    }
                )
            else:
                bin_missing.append(
                    "article {} meta_image: {}".format(article.pk, src)
                )

    log("  exporting articles ...")
    _dump_model(data, "articles", articles, extra_fn=_article_extra)
    log("  exporting remaining sections (review, production, metrics, ...) ...")

    _dump_model(
        data,
        "article_funding",
        submission_models.ArticleFunding.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "cited_references",
        submission_models.CitedReference.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "notes",
        submission_models.Note.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "article_stage_logs",
        submission_models.ArticleStageLog.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "workflow_logs",
        core_models.WorkflowLog.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "fixed_pub_check_items",
        journal_models.FixedPubCheckItems.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "prepub_checklist_items",
        journal_models.PrePublicationChecklistItem.objects.filter(
            article__journal=journal
        ),
    )
    _dump_model(
        data,
        "field_answers",
        submission_models.FieldAnswer.objects.filter(article__journal=journal),
    )

    # ---- authors -----------------------------------------------------------
    _dump_model(
        data,
        "frozen_authors",
        submission_models.FrozenAuthor.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "credit_records",
        submission_models.CreditRecord.objects.filter(
            frozen_author__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "controlled_affiliations",
        core_models.ControlledAffiliation.objects.filter(
            models.Q(account__pk__in=account_pks)
            | models.Q(frozen_author__article__journal=journal)
        ),
    )

    # ---- identifiers -------------------------------------------------------
    _dump_model(
        data,
        "identifiers",
        identifier_models.Identifier.objects.filter(article__journal=journal),
    )

    # ---- review ------------------------------------------------------------
    _dump_model(
        data,
        "review_rounds",
        review_models.ReviewRound.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "review_assignments",
        review_models.ReviewAssignment.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "review_answers",
        review_models.ReviewAssignmentAnswer.objects.filter(
            assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "review_answer_files",
        review_models.ReviewAssignmentAnswerFile.objects.filter(
            answer__assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "frozen_review_elements",
        review_models.FrozenReviewFormElement.objects.filter(
            answer__assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "reviewer_ratings",
        review_models.ReviewerRating.objects.filter(
            assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "revision_requests",
        review_models.RevisionRequest.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "revision_actions",
        review_models.RevisionAction.objects.filter(
            revisionrequest__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "editor_assignments",
        review_models.EditorAssignment.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "editor_overrides",
        review_models.EditorOverride.objects.filter(article__journal=journal),
    )
    _dump_model(
        data,
        "decision_drafts",
        review_models.DecisionDraft.objects.filter(article__journal=journal),
    )

    # ---- copyediting / production / proofing -------------------------------
    _dump_model(
        data,
        "copyedit_assignments",
        copyediting_models.CopyeditAssignment.objects.filter(
            article__journal=journal
        ),
    )
    _dump_model(
        data,
        "author_reviews",
        copyediting_models.AuthorReview.objects.filter(
            assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "production_assignments",
        production_models.ProductionAssignment.objects.filter(
            article__journal=journal
        ),
    )
    _dump_model(
        data,
        "typeset_tasks",
        production_models.TypesetTask.objects.filter(
            assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "proofing_assignments",
        proofing_models.ProofingAssignment.objects.filter(
            article__journal=journal
        ),
    )
    _dump_model(
        data,
        "proofing_rounds",
        proofing_models.ProofingRound.objects.filter(
            assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "proofing_tasks",
        proofing_models.ProofingTask.objects.filter(
            round__assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "typesetter_proofing_tasks",
        proofing_models.TypesetterProofingTask.objects.filter(
            proofing_task__round__assignment__article__journal=journal
        ),
    )
    _dump_model(
        data,
        "proofing_notes",
        proofing_models.Note.objects.filter(
            galley__article__journal=journal
        ),
    )

    # ---- core tasks ----------------------------------------------------------
    _dump_model(
        data,
        "tasks",
        core_models.Task.objects.filter(
            content_type__model="article", object_id__in=article_pks
        ),
    )

    # ---- metrics (optional app) ---------------------------------------------
    if HAS_METRICS:
        _dump_model(
            data,
            "altmetrics",
            metrics_models.AltMetric.objects.filter(article__journal=journal),
        )
        _dump_model(
            data,
            "article_links",
            metrics_models.ArticleLink.objects.filter(article__journal=journal),
        )
        _dump_model(
            data,
            "book_links",
            metrics_models.BookLink.objects.filter(article__journal=journal),
        )
        if include_article_access:
            _dump_model(
                data,
                "historic_article_access",
                metrics_models.HistoricArticleAccess.objects.filter(
                    article__journal=journal
                ),
            )
            _dump_model(
                data,
                "article_access",
                metrics_models.ArticleAccess.objects.filter(
                    article__journal=journal
                ),
            )
        else:
            log(
                "  skipping article access data "
                "(ArticleAccess, HistoricArticleAccess)"
            )

    # ---- TUW sync models (optional) ------------------------------------------
    if HAS_TUW_SYNC:
        _dump_model(
            data,
            "datacite",
            tuw_sync_models.DataCite.objects.filter(
                models.Q(article__journal=journal)
                | models.Q(issue__journal=journal)
            ),
        )
        _dump_model(
            data,
            "alma",
            tuw_sync_models.Alma.objects.filter(
                models.Q(article__journal=journal)
                | models.Q(issue__journal=journal)
            ),
        )
        _dump_model(
            data,
            "bulk_jobs",
            tuw_sync_models.BulkJob.objects.filter(journal=journal),
        )

    # ---- write manifest -------------------------------------------------------
    manifest_path = os.path.join(bundle_dir, "journal.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, default=str)

    log("  writing manifest ...")
    log("Wrote {}".format(manifest_path))
    log(
        "Bundle: {} objects, {} binary files".format(
            sum(len(v) for v in data.values() if isinstance(v, list)),
            len(binaries),
        )
    )
    if include_binaries and bin_missing:
        log(
            "  WARNING: {} referenced binary file(s) were NOT found on disk "
            "and are missing from the bundle (e.g. files/articles/<id>/, "
            "files/journals/<id>/ or MEDIA_ROOT):".format(len(bin_missing))
        )
        for detail in bin_missing[:20]:
            log("    - {}".format(detail))
        if len(bin_missing) > 20:
            log("    ... and {} more".format(len(bin_missing) - 20))
    return {
        "bundle_dir": bundle_dir,
        "manifest": manifest_path,
        "binaries": len(binaries),
    }


# ---------------------------------------------------------------------------
# IMPORT
# ---------------------------------------------------------------------------


def _load_bundle(bundle_dir):
    manifest_path = os.path.join(bundle_dir, "journal.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(
            "No journal.json found in {} (expected a bundle directory "
            "created by tuw_export_journal)".format(bundle_dir)
        )
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _rows(data, key):
    return data.get(key) or []


def _import_rows(
    data,
    key,
    model,
    extra=None,
    log=print,
    fk_remap=None,
    pk_remap=None,
    force=None,
    link_existing=False,
):
    """Import rows for ``key``, returning {old_pk: new_instance}.

    ``fk_remap``/``pk_remap`` are passed through to
    :func:`dict_to_model`/:func:`_save`; ``force`` maps field name -> value
    applied to every instance (e.g. ``journal=``).

    ``link_existing`` (for shared/global reference data such as roles,
    countries, organizations, keywords, ...): when a row with the same pk
    already exists, link to it instead of creating a copy. Copying would
    duplicate global rows and collide on unique/one-to-one constraints
    (e.g. OrganizationName.custom_label_for); on a fresh system the pk is
    absent, so the row is created with its source pk preserved.
    """
    mapping = {}
    _all_rows = _rows(data, key)
    last_beat = 0.0
    for _idx, row in enumerate(_all_rows, 1):
        if _all_rows and _idx % 100 == 0:
            now = time.monotonic()
            if now - last_beat >= 2.0:
                last_beat = now
                log("    {}: {}/{} ...".format(key, _idx, len(_all_rows)))
        values = dict(row.get("fields") or {})
        values["pk"] = row.get("pk")
        old_pk = row.get("pk")
        if link_existing and old_pk is not None:
            try:
                existing = model.objects.get(pk=old_pk)
                mapping[old_pk] = existing
                continue
            except (model.DoesNotExist, ValueError):
                pass
        try:
            instance = dict_to_model(
                model, values, fk_remap=fk_remap, **(force or {})
            )
        except Exception as exc:
            log("  warning: could not build {} {}: {}".format(key, row.get("pk"), exc))
            continue
        if extra:
            try:
                extra(instance, values)
            except Exception as exc:
                log(
                    "  warning: extra failed for {} {}: {}".format(
                        key, row.get("pk"), exc
                    )
                )
        try:
            _save(
                instance, values, pk_remap=pk_remap, log=log, fk_remap=fk_remap
            )
        except Exception as exc:
            log(
                "  warning: could not save {} {}: {}".format(
                    key, row.get("pk"), exc
                )
            )
            continue
        mapping[row.get("pk")] = instance
    if _rows(data, key):
        log("  imported {}: {}".format(key, len(mapping)))
    return mapping


def import_bundle(bundle_dir, code=None, domain=None, verbose=True):
    """Import a bundle created by ``export_bundle``.

    ``code``/``domain`` optionally rename the journal on import.
    Returns the imported Journal instance.
    """

    def log(msg):
        if verbose:
            print(msg)
            sys.stdout.flush()

    data = _load_bundle(bundle_dir)
    files_root = os.path.join(bundle_dir, "files")

    if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(
            "Unsupported bundle schema version: {}".format(data.get("schema_version"))
        )

    log("Importing bundle {} ...".format(bundle_dir))

    # Suspend m2m signals that create duplicate rows while the importer
    # restores m2ms explicitly (reconnected after the import transaction;
    # if the import fails, the transaction is rolled back and the command
    # process exits, so the signals need no restoration on that path):
    # - journal.issue_articles_change: post_add creates an ArticleOrdering
    #   row for every article added to an issue (the bundle's own
    #   article_ordering rows are imported separately).
    # - submission.backwards_compat_authors: post_add snapshots each author
    #   into a FrozenAuthor row (the bundle's frozen_authors are imported
    #   explicitly).
    from django.db.models.signals import m2m_changed as _m2m_changed

    _m2m_changed.disconnect(
        journal_models.issue_articles_change,
        sender=journal_models.Issue.articles.through,
    )
    _m2m_changed.disconnect(
        submission_models.backwards_compat_authors,
        sender=submission_models.Article.authors.through,
    )

    with transaction.atomic():
        log("  [1/5] preparing target system (base settings, xsl files) ...")
        # Ensure the target environment has base settings/roles in place.
        try:
            utils_install.update_settings()
        except Exception as exc:  # pragma: no cover
            log("  warning: update_settings failed: {}".format(exc))
        try:
            utils_install.update_xsl_files()
        except Exception as exc:  # pragma: no cover
            log("  warning: update_xsl_files failed: {}".format(exc))

        # ---- reference data that may differ in pk between installs ------------
        # content type pks can differ between installs; remap references
        ct_map = {}
        for row in _rows(data, "content_types"):
            try:
                ct_map[row["pk"]] = ContentType.objects.get(pk=row["pk"])
            except ContentType.DoesNotExist:
                continue
        ct_map.setdefault(
            ContentType.objects.get_for_model(submission_models.Article).pk,
            ContentType.objects.get_for_model(submission_models.Article),
        )

        # shared/global reference data: link to the existing row by pk when
        # present (same-system import), create fresh (source pk) otherwise
        roles = _import_rows(
            data, "roles", core_models.Role, log=log, link_existing=True
        )
        role_map = roles

        # ---- journal --------------------------------------------------------
        journal_fields = dict(data["journal"]["fields"])
        journal_fields["pk"] = data["journal"]["pk"]
        if code:
            journal_fields["code"] = code
        if domain:
            journal_fields["domain"] = domain

        # code/domain are globally unique; fail early with a clear message
        # instead of an IntegrityError partway through the import.
        new_code = journal_fields.get("code")
        if new_code and journal_models.Journal.objects.filter(
            code=new_code
        ).exists():
            raise ValueError(
                "A journal with code '{}' already exists on this system; "
                "pass --code to import under a different code.".format(new_code)
            )
        new_domain = journal_fields.get("domain")
        if new_domain and journal_models.Journal.objects.filter(
            domain=new_domain
        ).exists():
            raise ValueError(
                "A journal with domain '{}' already exists on this system; "
                "pass --domain to import under a different domain.".format(
                    new_domain
                )
            )

        # The journal gets a fresh pk on import; all bundle references are
        # remapped through pk_map. Do NOT copy the source pk over (it would
        # clobber an existing journal when importing into the same system).
        journal = journal_models.Journal()
        for name, value in journal_fields.items():
            if name == "pk":
                continue
            try:
                field = journal._meta.get_field(name)
            except Exception:
                continue
            if field.primary_key:
                continue
            if field.many_to_many:
                continue  # restored later via .set()
            setattr(journal, name, _coerce(field, value))
        apply_translations(journal, data["journal"]["fields"])
        journal.save()  # triggers default section/workflow/config signals
        log("  journal '{}' (pk {}) created".format(journal.code, journal.pk))
        global _IMPORT_JOURNAL_REMAP, _IMPORT_JOURNAL_MODEL
        old_journal_pk = data["journal"]["pk"]
        # pk_map maps the source journal pk to the NEW journal instance.
        # It must hold instances, not ints: fk_remaps pass the value straight
        # to setattr(instance, <fk_field>, ...), which requires a model
        # instance (an int raises "must be a Journal instance").
        pk_map = {old_journal_pk: journal}
        _IMPORT_JOURNAL_REMAP = {old_journal_pk: journal}
        _IMPORT_JOURNAL_MODEL = journal_models.Journal
        journal_ct = ContentType.objects.get_for_model(journal)

        # journal settings must be in place before issues are imported
        # (Issue.save() reads journal settings to render display titles).
        log("  [2/5] importing journal settings ...")
        _import_journal_settings(data, journal, log)

        # interests (m2m of account; must exist before accounts are saved)
        interests = _import_rows(
            data, "interests", core_models.Interest, log=log, link_existing=True
        )

        # ---- accounts ---------------------------------------------------------
        # On a same-system import the bundle's accounts usually already exist
        # (they are shared reference data). Link to the existing account
        # instead of creating a duplicate copy: duplicates break role
        # uniqueness and orphan the journal's users.
        accounts = {}
        linked_accounts = 0
        created_accounts = 0
        _acc_rows = _rows(data, "accounts")
        _acc_total = len(_acc_rows)
        log("  [3/5] importing {} accounts ...".format(_acc_total))
        for _acc_idx, row in enumerate(_acc_rows, 1):
            if verbose and _acc_total and _acc_idx % 100 == 0:
                log("    accounts: {}/{}".format(_acc_idx, _acc_total))
            values = dict(row["fields"])
            email = values.get("email")
            values.pop("password", None)
            existing = None
            if email:
                try:
                    existing = core_models.Account.objects.get(
                        models.Q(email__iexact=email)
                        | models.Q(username__iexact=email)
                    )
                except core_models.Account.DoesNotExist:
                    existing = None
                except core_models.Account.MultipleObjectsReturned:
                    # ambiguous on this system; fall through to creating a
                    # fresh copy rather than guessing
                    existing = None
            if existing is not None and email:
                accounts[row["pk"]] = existing
                linked_accounts += 1
                continue
            try:
                instance = dict_to_model(core_models.Account, values)
                instance.set_password(
                    "janeway-imported-{}-unusable".format(uuid_lib.uuid4().hex[:8])
                )
                _save(instance, values, log=log)
                created_accounts += 1
                accounts[row["pk"]] = instance
            except Exception:
                log(
                    "  warning: could not import account {} ({})".format(
                        email or row["pk"], values.get("pk")
                    )
                )
                continue
        if _rows(data, "accounts"):
            log(
                "  imported accounts: {} ({} linked, {} created)".format(
                    len(accounts), linked_accounts, created_accounts
                )
            )

        # ---- shared reference data ------------------------------------------
        # (global rows: link to the existing row by pk on a same-system
        # import, create fresh with the source pk on a fresh system)
        countries = _import_rows(
            data, "countries", core_models.Country, log=log, link_existing=True
        )
        locations = _import_rows(
            data, "locations", core_models.Location, log=log, link_existing=True
        )
        organizations = _import_rows(
            data, "organizations", core_models.Organization, log=log,
            link_existing=True,
        )
        organization_names = _import_rows(
            data, "organization_names", core_models.OrganizationName, log=log,
            link_existing=True,
        )
        # (Organization.locations m2m is restored at save time via M2M_RESTORE)

        # ---- roles / journal-level users --------------------------------------
        account_roles = _import_rows(
            data,
            "account_roles",
            core_models.AccountRole,
            log=log,
            fk_remap={"journal": pk_map, "user": accounts, "role": role_map},
        )
        editorial_groups = _import_rows(
            data, "editorial_groups", core_models.EditorialGroup, log=log,
            fk_remap={"journal": pk_map},
        )
        editorial_group_members = _import_rows(
            data,
            "editorial_group_members",
            core_models.EditorialGroupMember,
            log=log,
            fk_remap={"group": editorial_groups, "user": accounts},
        )

        # ---- sections -----------------------------------------------------------
        # the journal-creation signal already created a default "Article"
        # section; drop it (only when the bundle carries sections) so the
        # imported sections are authoritative.
        if _rows(data, "sections"):
            for section in submission_models.Section.objects.filter(journal=journal):
                if not section.article_set.exists():
                    section.delete()
        # account pks may differ from the source when accounts were linked
        # to pre-existing users; remap for the account m2ms (editors, ...)
        account_pk_remap = {
            "core.Account": {pk: account.pk for pk, account in accounts.items()}
        }
        sections = _import_rows(
            data, "sections", submission_models.Section, log=log,
            pk_remap=account_pk_remap,
            fk_remap={"journal": pk_map},
        )

        # ---- licenses (deduped against the signal-created CC defaults) ----------
        existing_licenses = {
            lic.short_name: lic
            for lic in submission_models.Licence.objects.filter(journal=journal)
        }
        licenses = {}
        for row in _rows(data, "licenses"):
            values = dict(row["fields"])
            values["pk"] = row["pk"]
            short_name = values.get("short_name")
            if short_name and short_name in existing_licenses:
                instance = existing_licenses[short_name]
            else:
                values.pop("pk", None)
                instance = dict_to_model(
                    submission_models.Licence, values, journal=journal
                )
                try:
                    _save(instance, values, log=log)
                except Exception as exc:
                    log("  warning: license {}: {}".format(short_name, exc))
                    continue
            licenses[row["pk"]] = instance
        if _rows(data, "licenses"):
            log("  imported licenses: {}".format(len(licenses)))

        issue_types = _import_rows(
            data, "issue_types", journal_models.IssueType, log=log,
            fk_remap={"journal": pk_map},
        )

        # ---- submission configuration (created by the journal signal) ----------
        sub_config_row = data.get("submission_config")
        if sub_config_row:
            values = dict(sub_config_row["fields"])
            try:
                sub_config = submission_models.SubmissionConfiguration.objects.get(
                    journal=journal
                )
            except submission_models.SubmissionConfiguration.DoesNotExist:
                sub_config = submission_models.SubmissionConfiguration.objects.create(
                    journal=journal
                )
            for name, value in values.items():
                if name == "pk" or name.endswith("_id"):
                    continue
                try:
                    field = sub_config._meta.get_field(name)
                except Exception:
                    continue
                if field.primary_key:
                    continue  # keep the fresh pk; journal FK is already set
                if field.many_to_many:
                    continue  # m2ms are not direct-assignable
                setattr(sub_config, name, _coerce(field, value))
            # default_license / default_section may point at freshly imported rows
            lic_ref = values.get("default_license_id")
            if lic_ref and lic_ref in licenses:
                sub_config.default_license = licenses[lic_ref]
            sec_ref = values.get("default_section_id")
            if sec_ref and sec_ref in sections:
                sub_config.default_section = sections[sec_ref]
            apply_translations(sub_config, values)
            sub_config.save()
            log("  imported submission configuration")

        fields_custom = _import_rows(
            data, "fields_custom", submission_models.Field, log=log,
            fk_remap={"journal": pk_map},
        )

        # the journal signal pre-created default submission items; drop them
        # (only when the bundle carries items) so the imported items are
        # authoritative (title is unique per journal).
        if _rows(data, "submission_items"):
            try:
                for item in cms_models.SubmissionItem.objects.filter(journal=journal):
                    item.delete()
            except Exception:  # pragma: no cover
                pass
        submission_items = _import_rows(
            data,
            "submission_items",
            cms_models.SubmissionItem,
            log=log,
            force={"journal": journal},
        )

        # ---- workflow (needed before articles: submission logs stage changes) --
        # the journal signal pre-created a default workflow with 4 elements;
        # drop them (only when the bundle carries elements) so the imported
        # elements are authoritative and the defaults do not linger as orphans
        if _rows(data, "workflow_elements"):
            for element in core_models.WorkflowElement.objects.filter(
                journal=journal
            ):
                element.delete()
        workflow_elements = _import_rows(
            data, "workflow_elements", core_models.WorkflowElement, log=log,
            fk_remap={"journal": pk_map},
        )
        workflow_row = data.get("workflow")
        if workflow_row:
            auto_workflow = core_models.Workflow.objects.filter(
                journal=journal
            ).first()
            if auto_workflow is not None:
                # the journal signal created a default workflow; replace it
                # (only when the bundle actually carries a workflow).
                auto_workflow.delete()
            values = dict(workflow_row["fields"])
            values.pop("pk", None)
            workflow_obj = dict_to_model(core_models.Workflow, values, journal=journal)
            try:
                _save(workflow_obj, values, log=log)
                element_pks = workflow_row.get("elements") or []
                if element_pks:
                    # link ONLY the freshly imported elements; a raw-pk
                    # fallback here would point at the SOURCE journal's rows
                    linked_elements = [
                        obj
                        for p in element_pks
                        for obj in [workflow_elements.get(p)]
                        if obj is not None
                    ]
                    workflow_obj.elements.set(linked_elements)
                log("  imported workflow")
            except Exception as exc:
                log("  warning: could not import workflow: {}".format(exc))

        # the journal signal created a default review form; drop it (only when
        # the bundle carries forms) so the imported form is authoritative
        if _rows(data, "review_forms"):
            for form in review_models.ReviewForm.objects.filter(journal=journal):
                form.delete()
        review_forms = _import_rows(
            data, "review_forms", review_models.ReviewForm, log=log,
            fk_remap={"journal": pk_map},
        )
        review_form_elements = _import_rows(
            data, "review_form_elements", review_models.ReviewFormElement, log=log,
            fk_remap={"reviewform": review_forms},
        )

        # ---- files (before galleys/articles that reference them) ---------------
        # Note: File.article_id is a plain int column (not an FK); the old
        # article pks land on the fresh copies and are re-pointed at the
        # imported articles by the two-phase article_id remap below.
        files_map = _import_rows(
            data, "files", core_models.File, log=log,
            fk_remap={"owner": accounts, "text": None},
        )

        file_histories = _import_rows(
            data, "file_histories", core_models.FileHistory, log=log,
            fk_remap={"owner": accounts, "text": None},
        )
        # file <-> history m2m (match via files_map: bundle pk -> imported
        # instance; the imported pk differs on a same-system import)
        for row in _rows(data, "files"):
            file_obj = files_map.get(row.get("pk"))
            if file_obj is None:
                continue
            history_pks = (row.get("fields") or {}).get("history") or []
            if history_pks:
                file_obj.history.set(
                    core_models.FileHistory.objects.filter(
                        pk__in=_pks(history_pks, file_histories)
                    )
                )

        # ---- news / tags / carousel ----------------------------------------------
        news = _import_rows(
            data, "news", comms_models.NewsItem, log=log,
            fk_remap={
                "posted_by": accounts,
                "large_image_file": files_map,
            },
            force={
                # re-anchor the generic FK on the imported journal (only the
                # freshly imported rows, never other journals' rows)
                "content_type": journal_ct,
                "object_id": journal.pk,
            },
        )
        news_tags = _import_rows(
            data, "news_tags", comms_models.Tag, log=log, link_existing=True
        )

        carousel_obj = None
        carousel_row = data.get("carousel")
        if carousel_row:
            values = dict(carousel_row["fields"])
            values["pk"] = carousel_row["pk"]
            carousel_obj = dict_to_model(carousel_models.Carousel, values)
            try:
                _save(carousel_obj, values, log=log)
                log("  imported carousel")
            except Exception as exc:
                log("  warning: could not import carousel: {}".format(exc))
                carousel_obj = None

        # ---- issues ---------------------------------------------------------------
        issues = {}
        for row in _rows(data, "issues"):
            values = dict(row["fields"])
            values["pk"] = row["pk"]
            try:
                issue_obj = dict_to_model(
                    journal_models.Issue, values,
                    journal=journal,
                    fk_remap={"issue_type": issue_types},
                )
                _save(issue_obj, values, log=log)
                issues[row["pk"]] = issue_obj
            except Exception as exc:
                log("  warning: could not import issue {}: {}".format(row["pk"], exc))
        if _rows(data, "issues"):
            log("  imported issues: {}".format(len(issues)))

        # issue editors (through model) + section/article ordering
        issue_editors = _import_rows(
            data,
            "issue_editors",
            journal_models.IssueEditor,
            log=log,
            fk_remap={"issue": issues, "account": accounts},
        )
        # issue.editors is a through-based m2m: the IssueEditor rows above
        # already created the through records, so the m2m is restored.
        section_ordering = _import_rows(
            data,
            "section_ordering",
            journal_models.SectionOrdering,
            log=log,
            fk_remap={"issue": issues, "section": sections},
        )
        _import_rows(
            data,
            "issue_galleys",
            journal_models.IssueGalley,
            log=log,
            fk_remap={"issue": issues, "file": files_map},
        )

        # ---- articles ---------------------------------------------------------------
        # Note: pks are not preserved for articles because Article.save()
        # queries the db by pk; the new pks are remapped everywhere below.
        _art_rows = _rows(data, "articles")
        log("  importing {} articles ...".format(len(_art_rows)))
        articles = {}
        for _art_idx, row in enumerate(_art_rows, 1):
            if verbose and _art_rows and _art_idx % 50 == 0:
                log("    articles: {}/{}".format(_art_idx, len(_art_rows)))
            values = dict(row["fields"])
            values["pk"] = row["pk"]
            # defer galley/issue/file FKs to a second pass
            values.pop("render_galley_id", None)
            values.pop("primary_issue_id", None)
            values.pop("projected_issue_id", None)
            values.pop("large_image_file_id", None)
            values.pop("thumbnail_image_id", None)
            values.pop("thumbnail_image_file_id", None)
            values.pop("pk", None)  # Article.save() is pk-sensitive
            try:
                article_obj = dict_to_model(
                    submission_models.Article,
                    values,
                    journal=journal,
                    fk_remap={
                        "owner": accounts,
                        "correspondence_author": accounts,
                        "section": sections,
                        "license": licenses,
                        "preprint_journal_article": None,
                    },
                )
                _save(article_obj, values, log=log)
                articles[row["pk"]] = article_obj
            except Exception as exc:
                log("  warning: could not import article {}: {}".format(row["pk"], exc))
        if _rows(data, "articles"):
            log("  imported articles: {}".format(len(articles)))

        # self-reference: preprint_journal_article
        for row in _rows(data, "articles"):
            values = row.get("fields") or {}
            ref = values.get("preprint_journal_article_id")
            article_obj = articles.get(row["pk"])
            if article_obj and ref and ref in articles:
                article_obj.preprint_journal_article = articles[ref]
                article_obj.save()

        # ---- remap raw article_id columns (files/histories) -----------------------
        # core.File.article_id and core.FileHistory.article_id are plain
        # PositiveIntegerFields (not FKs), so they were imported with the old
        # article pks. Remap them now that the articles exist, in two phases
        # (via unique placeholders) so overlapping pk ranges cannot collide.
        # IMPORTANT: on a same-system import the update must be restricted to
        # the rows imported from THIS bundle; filtering by article_id alone
        # would re-point the SOURCE journal's files at the new articles.
        imported_file_pks = [obj.pk for obj in files_map.values() if obj.pk]
        imported_history_pks = [obj.pk for obj in file_histories.values() if obj.pk]
        placeholders = {}
        for idx, old_pk in enumerate(articles):
            placeholders[old_pk] = (1000000000 + idx, articles[old_pk].pk)
        for old_pk, (placeholder, _new_pk) in placeholders.items():
            core_models.File.objects.filter(
                article_id=old_pk, pk__in=imported_file_pks
            ).update(article_id=placeholder)
            core_models.FileHistory.objects.filter(
                article_id=old_pk, pk__in=imported_history_pks
            ).update(article_id=placeholder)
        for old_pk, (placeholder, new_pk) in placeholders.items():
            core_models.File.objects.filter(
                article_id=placeholder, pk__in=imported_file_pks
            ).update(article_id=new_pk)
            core_models.FileHistory.objects.filter(
                article_id=placeholder, pk__in=imported_history_pks
            ).update(article_id=new_pk)

        # ---- article ordering within issues ----------------------------------------
        _import_rows(
            data,
            "article_ordering",
            journal_models.ArticleOrdering,
            log=log,
            fk_remap={"issue": issues, "article": articles, "section": sections},
        )

        # ---- article detail rows ---------------------------------------------------
        _import_rows(
            data, "article_funding", submission_models.ArticleFunding, log=log,
            fk_remap={"article": articles},
        )
        _import_rows(
            data, "cited_references", submission_models.CitedReference, log=log,
            fk_remap={"article": articles},
        )
        _import_rows(
            data, "notes", submission_models.Note, log=log,
            fk_remap={"article": articles, "creator": accounts},
        )
        _import_rows(
            data, "article_stage_logs", submission_models.ArticleStageLog, log=log,
            fk_remap={"article": articles},
        )
        _import_rows(
            data, "workflow_logs", core_models.WorkflowLog, log=log,
            fk_remap={"article": articles, "element": None, "user": accounts},
        )
        _import_rows(
            data, "fixed_pub_check_items", journal_models.FixedPubCheckItems, log=log,
            fk_remap={"article": articles},
        )
        _import_rows(
            data, "prepub_checklist_items",
            journal_models.PrePublicationChecklistItem,
            log=log,
            fk_remap={"article": articles, "completed_by": accounts},
        )
        _import_rows(
            data, "field_answers", submission_models.FieldAnswer, log=log,
            fk_remap={"field": fields_custom, "article": articles},
        )

        # ---- frozen authors + affiliations -------------------------------------------
        frozen_authors = _import_rows(
            data, "frozen_authors", submission_models.FrozenAuthor, log=log,
            fk_remap={"article": articles, "author": accounts},
        )
        _import_rows(
            data, "credit_records", submission_models.CreditRecord, log=log,
            fk_remap={"frozen_author": frozen_authors},
        )
        # Controlled affiliations come in two flavours:
        # - frozen-author-scoped: article snapshots that must be created for
        #   the freshly imported FrozenAuthor rows.
        # - account-scoped (frozen_author null): the account's own persistent
        #   affiliations -- shared reference data that already exists on a
        #   same-system import, so link to it instead of duplicating.
        _ca_remap = {
            "account": accounts,
            "frozen_author": frozen_authors,
            "organization": organizations,
            "preprint_author": None,
        }
        for row in _rows(data, "controlled_affiliations"):
            values = dict(row.get("fields") or {})
            values["pk"] = row.get("pk")
            if values.get("frozen_author_id") in (None, ""):
                # account-scoped: link to the existing row when present
                try:
                    core_models.ControlledAffiliation.objects.get(
                        pk=row.get("pk")
                    )
                    continue
                except (
                    core_models.ControlledAffiliation.DoesNotExist,
                    ValueError,
                ):
                    pass
            try:
                instance = dict_to_model(
                    core_models.ControlledAffiliation, values, fk_remap=_ca_remap
                )
                _save(instance, values, log=log, fk_remap=_ca_remap)
            except Exception as exc:
                log(
                    "  warning: could not save controlled_affiliations {}: {}".format(
                        row.get("pk"), exc
                    )
                )
        if _rows(data, "controlled_affiliations"):
            log(
                "  imported controlled_affiliations: {}".format(
                    len(_rows(data, "controlled_affiliations"))
                )
            )

        # ---- keywords ------------------------------------------------------------------
        keywords = _import_rows(
            data, "keywords", submission_models.Keyword, log=log,
            link_existing=True,
        )
        _import_rows(
            data, "keyword_articles", submission_models.KeywordArticle, log=log,
            fk_remap={"keyword": keywords, "article": articles},
        )
        _import_rows(
            data, "publisher_notes", submission_models.PublisherNote, log=log,
            fk_remap={"creator": accounts},
        )

        # ---- identifiers ------------------------------------------------------------------
        _import_rows(
            data, "identifiers", identifier_models.Identifier, log=log,
            fk_remap={"article": articles},
        )

        # ---- galleys ----------------------------------------------------------------------
        galleys = _import_rows(
            data, "galleys", core_models.Galley, log=log,
            fk_remap={"article": articles, "file": files_map, "css_file": files_map},
        )
        # xsl_file references are resolved by the generic FK lookup (when
        # the target happens to have the same pk); otherwise Galley.save()
        # assigns the default XSL for xml galleys.

        _import_rows(
            data, "supplementary_files", core_models.SupplementaryFile, log=log,
            fk_remap={"file": files_map},
        )

        # ---- review / copyedit / production / proofing --------------------------------------
        review_rounds = _import_rows(
            data, "review_rounds", review_models.ReviewRound, log=log,
            fk_remap={"article": articles},
        )
        review_assignments = _import_rows(
            data, "review_assignments", review_models.ReviewAssignment, log=log,
            fk_remap={
                "article": articles,
                "reviewer": accounts,
                "editor": accounts,
                "review_round": review_rounds,
                "form": review_forms,
                "review_file": files_map,
            },
        )
        review_answers = _import_rows(
            data, "review_answers", review_models.ReviewAssignmentAnswer, log=log,
            fk_remap={
                "assignment": review_assignments,
                "original_element": review_form_elements,
            },
        )
        _import_rows(
            data, "review_answer_files", review_models.ReviewAssignmentAnswerFile, log=log,
            fk_remap={"answer": review_answers, "file": files_map},
        )
        _import_rows(
            data, "frozen_review_elements", review_models.FrozenReviewFormElement, log=log,
            fk_remap={"form_element": review_form_elements, "answer": review_answers},
        )
        _import_rows(
            data, "reviewer_ratings", review_models.ReviewerRating, log=log,
            fk_remap={"assignment": review_assignments, "rater": accounts},
        )
        revision_requests = _import_rows(
            data, "revision_requests", review_models.RevisionRequest, log=log,
            fk_remap={"article": articles, "editor": accounts},
        )
        _import_rows(
            data, "revision_actions", review_models.RevisionAction, log=log,
            fk_remap={"revisionrequest": revision_requests, "user": accounts},
        )
        _import_rows(
            data, "editor_assignments", review_models.EditorAssignment, log=log,
            fk_remap={"article": articles},
        )
        _import_rows(
            data, "editor_overrides", review_models.EditorOverride, log=log,
            fk_remap={"article": articles},
        )
        _import_rows(
            data, "decision_drafts", review_models.DecisionDraft, log=log,
            fk_remap={
                "article": articles,
                "editor": accounts,
                "section_editor": accounts,
            },
        )
        copyedit_assignments = _import_rows(
            data, "copyedit_assignments", copyediting_models.CopyeditAssignment, log=log,
            fk_remap={"article": articles, "copyeditor": accounts, "editor": accounts},
        )
        _import_rows(
            data, "author_reviews", copyediting_models.AuthorReview, log=log,
            fk_remap={"author": accounts, "assignment": copyedit_assignments},
        )
        production_assignments = _import_rows(
            data, "production_assignments",
            production_models.ProductionAssignment,
            log=log,
            fk_remap={
                "article": articles,
                "production_manager": accounts,
                "editor": accounts,
            },
        )
        _import_rows(
            data,
            "typeset_tasks",
            production_models.TypesetTask,
            log=log,
            fk_remap={
                "assignment": production_assignments,
                "typesetter": accounts,
            },
        )
        proofing_assignments = _import_rows(
            data, "proofing_assignments", proofing_models.ProofingAssignment, log=log,
            fk_remap={
                "article": articles,
                "proofing_manager": accounts,
                "editor": accounts,
            },
        )
        proofing_rounds = _import_rows(
            data, "proofing_rounds", proofing_models.ProofingRound, log=log,
            fk_remap={"assignment": proofing_assignments},
        )
        proofing_tasks = _import_rows(
            data, "proofing_tasks", proofing_models.ProofingTask, log=log,
            fk_remap={"round": proofing_rounds, "proofreader": accounts},
        )
        _import_rows(
            data,
            "typesetter_proofing_tasks",
            proofing_models.TypesetterProofingTask,
            log=log,
            fk_remap={
                "proofing_task": proofing_tasks,
                "typesetter": accounts,
            },
        )
        proofing_notes = _import_rows(
            data, "proofing_notes", proofing_models.Note, log=log,
            fk_remap={"galley": galleys, "creator": accounts},
        )
        task_events = _import_rows(
            data, "task_events", core_models.TaskCompleteEvents, log=log,
            link_existing=True,
        )
        _import_rows(
            data, "tasks", core_models.Task, log=log,
            fk_remap={
                "content_type": ct_map,
                "completed_by": accounts,
                # generic FK: object_id holds the source article pk
                "object_id": lambda ref: articles.get(int(ref)),
            },
            pk_remap=account_pk_remap,
        )

        # ---- metrics / tuw_sync (optional apps) ----------------------------------------
        if HAS_METRICS:
            _import_rows(
                data, "altmetrics", metrics_models.AltMetric, log=log,
                fk_remap={"article": articles},
            )
            _import_rows(
                data, "article_links", metrics_models.ArticleLink, log=log,
                fk_remap={"article": articles},
            )
            _import_rows(
                data, "book_links", metrics_models.BookLink, log=log,
                fk_remap={"article": articles},
            )
            _import_rows(
                data, "historic_article_access",
                metrics_models.HistoricArticleAccess,
                log=log,
                fk_remap={"article": articles},
            )
            _import_rows(
                data, "article_access", metrics_models.ArticleAccess, log=log,
                fk_remap={"article": articles},
            )
        if HAS_TUW_SYNC:
            _import_rows(
                data, "datacite", tuw_sync_models.DataCite, log=log,
                fk_remap={"article": articles, "issue": issues},
            )
            _import_rows(
                data, "alma", tuw_sync_models.Alma, log=log,
                fk_remap={"article": articles, "issue": issues},
            )
            _import_rows(
                data, "bulk_jobs", tuw_sync_models.BulkJob, log=log,
                fk_remap={"journal": pk_map},
            )

        # ---- second-pass m2ms whose targets were imported after the owner ----
        # proofing_notes are imported after proofing_tasks, so the
        # ProofingTask.notes m2m was not restored at save time.
        for row in _rows(data, "proofing_tasks"):
            note_pks = (row.get("fields") or {}).get("notes") or []
            if not note_pks:
                continue
            task_obj = proofing_tasks.get(row["pk"])
            if task_obj is None:
                continue
            try:
                task_obj.notes.set(
                    proofing_models.Note.objects.filter(
                        pk__in=_pks(note_pks, proofing_notes)
                    )
                )
            except Exception as exc:
                log("  warning: could not restore proofing task notes: {}".format(exc))

        # ---- second-pass FKs that point at objects created above -----------------------
        # issues
        for row in _rows(data, "issues"):
            values = row.get("fields") or {}
            issue_obj = issues.get(row["pk"])
            if issue_obj is None:
                continue
            # articles m2m
            article_refs = values.get("articles") or []
            if article_refs:
                issue_obj.articles.set(
                    [articles[ref] for ref in article_refs if ref in articles]
                )
        # articles -> galley / issues / image files
        for row in _rows(data, "articles"):
            values = row.get("fields") or {}
            article_obj = articles.get(row["pk"])
            if article_obj is None:
                continue
            changed = False
            galley_ref = values.get("render_galley_id")
            if galley_ref and galley_ref in galleys:
                article_obj.render_galley = galleys[galley_ref]
                changed = True
            issue_ref = values.get("primary_issue_id")
            if issue_ref and issue_ref in issues:
                article_obj.primary_issue = issues[issue_ref]
                changed = True
            issue_ref = values.get("projected_issue_id")
            if issue_ref and issue_ref in issues:
                article_obj.projected_issue = issues[issue_ref]
                changed = True
            file_ref = values.get("large_image_file_id")
            if file_ref and file_ref in files_map:
                article_obj.large_image_file = files_map[file_ref]
                changed = True
            file_ref = values.get("thumbnail_image_file_id")
            if file_ref and file_ref in files_map:
                article_obj.thumbnail_image_file = files_map[file_ref]
                changed = True
            if changed:
                article_obj.save()

        # article m2ms: files / publisher notes / supplementary files
        for row in _rows(data, "articles"):
            values = row.get("fields") or {}
            article_obj = articles.get(row["pk"])
            if article_obj is None:
                continue
            for m2m_name in (
                "manuscript_files",
                "data_figure_files",
                "source_files",
            ):
                pks = values.get(m2m_name) or []
                if pks:
                    getattr(article_obj, m2m_name).set(
                        core_models.File.objects.filter(
                            pk__in=_pks(pks, files_map)
                        )
                    )
            note_pks = values.get("publisher_notes") or []
            if note_pks:
                article_obj.publisher_notes.set(
                    submission_models.PublisherNote.objects.filter(
                        pk__in=note_pks
                    )
                )
            supp_pks = values.get("supplementary_files") or []
            if supp_pks:
                article_obj.supplementary_files.set(
                    core_models.SupplementaryFile.objects.filter(pk__in=supp_pks)
                )
            author_pks = values.get("authors") or []
            if author_pks:
                article_obj.authors.set(
                    core_models.Account.objects.filter(
                        pk__in=_pks(author_pks, accounts)
                    )
                )

        # galley m2ms (images); xsl references are re-matched by label below,
        # because xsl pks are global (the row may map to a shared default)
        xsl_label_by_pk = {
            row["pk"]: (row.get("fields") or {}).get("label")
            for row in _rows(data, "xsl_files")
        }
        for row in _rows(data, "galleys"):
            values = row.get("fields") or {}
            galley = galleys.get(row["pk"])
            if galley is None:
                continue
            image_pks = values.get("images") or []
            if image_pks:
                galley.images.set(
                    core_models.File.objects.filter(
                        pk__in=_pks(image_pks, files_map)
                    )
                )
            xsl_ref = values.get("xsl_file_id")
            if xsl_ref:
                label = xsl_label_by_pk.get(xsl_ref)
                if label:
                    xsl_obj = core_models.XSLFile.objects.filter(
                        label=label
                    ).first()
                    if xsl_obj is not None and galley.xsl_file_id != xsl_obj.pk:
                        galley.xsl_file = xsl_obj
                        galley.save()

        # (m2ms for review rounds / tasks / galleys / etc. are restored via
        # _restore_m2m inside _save, using M2M_RESTORE)

        # ---- journal-level rows -------------------------------------------------------
        # XSL files: XSLFile.label is unique across the whole installation,
        # so rows are matched by label against the global defaults that
        # update_xsl_files() created; only genuinely new labels are inserted.
        xsl_files = {}
        for row in _rows(data, "xsl_files"):
            values = dict(row["fields"])
            label = values.get("label")
            try:
                xsl = core_models.XSLFile.objects.get(label=label)
            except core_models.XSLFile.DoesNotExist:
                values.pop("pk", None)
                xsl = dict_to_model(core_models.XSLFile, values, journal=journal)
                try:
                    _save(xsl, values, log=log)
                except Exception as exc:
                    log("  warning: could not import xsl '{}': {}".format(label, exc))
                    continue
            xsl_files[row["pk"]] = xsl
        if _rows(data, "xsl_files"):
            log("  imported xsl files: {}".format(len(xsl_files)))
        _import_rows(
            data, "domain_aliases", core_models.DomainAlias, log=log,
            fk_remap={"journal": pk_map},
        )
        _import_rows(
            data, "access_requests", core_models.AccessRequest, log=log,
            fk_remap={"journal": pk_map, "user": accounts, "role": role_map},
        )
        _import_rows(
            data, "notifications", journal_models.Notifications, log=log,
            fk_remap={"journal": pk_map, "user": accounts},
        )
        _import_rows(
            data,
            "pinned_articles",
            journal_models.PinnedArticle,
            log=log,
            fk_remap={"journal": pk_map, "article": articles},
        )
        _import_rows(
            data, "preset_pub_check_items",
            journal_models.PresetPublicationCheckItem,
            log=log,
            fk_remap={"journal": pk_map},
        )

        # content_type is forced onto the imported journal for every
        # generic-FK row (only the freshly imported rows are touched, so
        # same-system imports never re-anchor other journals' rows)
        _import_rows(
            data,
            "contacts",
            core_models.Contacts,
            log=log,
            force={
                "content_type": journal_ct,
                "object_id": journal.pk,
            },
        )
        _import_rows(
            data,
            "homepage_elements",
            core_models.HomepageElement,
            log=log,
            force={
                "content_type": journal_ct,
                "object_id": journal.pk,
            },
        )

        # ---- cms pages / navigation -------------------------------------------------------
        cms_pages = _import_rows(
            data,
            "cms_pages",
            cms_models.Page,
            log=log,
            force={
                "content_type": journal_ct,
                "object_id": journal.pk,
            },
        )
        _import_rows(
            data,
            "cms_navigation_items",
            cms_models.NavigationItem,
            log=log,
            fk_remap={"page": cms_pages},
            force={
                "content_type": journal_ct,
                "object_id": journal.pk,
            },
        )

        # cms media files (rows dumped with pk preserved)
        cms_media_files = _import_rows(
            data, "cms_media_files", cms_models.MediaFile, log=log,
            fk_remap={"journal": pk_map},
        )

        # ---- carousel m2ms + journal keywords -----------------------------------------------
        if carousel_obj:
            carousel_row = data.get("carousel") or {}
            values = carousel_row.get("fields") or {}
            article_pks = values.get("articles") or []
            if article_pks:
                carousel_obj.articles.set(
                    submission_models.Article.objects.filter(
                        pk__in=_pks(article_pks, articles)
                    )
                )
            news_pks = values.get("news_articles") or []
            if news_pks:
                carousel_obj.news_articles.set(
                    comms_models.NewsItem.objects.filter(
                        pk__in=_pks(news_pks, news)
                    )
                )
            issue_pks = values.get("issues") or []
            if issue_pks:
                carousel_obj.issues.set(
                    journal_models.Issue.objects.filter(
                        pk__in=_pks(issue_pks, issues)
                    )
                )
            journal.carousel = carousel_obj
            journal.save()

        journal_keyword_pks = (
            (data["journal"].get("fields") or {}).get("keywords") or []
        )
        if journal_keyword_pks:
            journal.keywords.set(
                submission_models.Keyword.objects.filter(
                    pk__in=_pks(journal_keyword_pks, keywords)
                )
            )

        # ---- binaries -----------------------------------------------------------------------
        if os.path.isdir(files_root):
            _bin_entries = data.get("binaries", [])
            log("  [4/5] copying {} binary files ...".format(len(_bin_entries)))
            for _bin_idx, entry in enumerate(_bin_entries, 1):
                if verbose and _bin_entries and _bin_idx % 50 == 0:
                    log("    binaries: {}/{}".format(_bin_idx, len(_bin_entries)))
                _import_binary_entry(
                    entry,
                    files_root,
                    {
                        "journal": journal,
                        "issues": issues,
                        "articles": articles,
                        "files": files_map,
                        "accounts": accounts,
                    },
                    log,
                )
        else:
            log("  no files/ directory in bundle; skipping binaries")

        log("  [5/5] finalizing (file name remapping, journal fields) ...")
        # ---- pk-embedded FileField name remapping ----------------------------------------------
        _remap_file_field_names(data, journal, issues, articles, files_map, log)

        # ---- remaining journal FKs ----------------------------------------------------------------
        _finalize_journal(data, journal, files_map, issues, log)

    # re-enable the m2m signals suspended at the start of the import
    _m2m_changed.connect(
        journal_models.issue_articles_change,
        sender=journal_models.Issue.articles.through,
    )
    _m2m_changed.connect(
        submission_models.backwards_compat_authors,
        sender=submission_models.Article.authors.through,
    )

    log("Import complete: journal '{}' (pk {})".format(journal.code, journal.pk))
    return journal


def _remap_file_field_names(data, journal, issues, articles, files_map, log):
    """Fix FileField names that embed the *old* pk of their owner."""

    def media_name(old_name, new_name):
        src = os.path.join(_media_root(), old_name)
        dst = os.path.join(_media_root(), new_name)
        if new_name and os.path.isfile(src) and os.path.abspath(src) != os.path.abspath(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
        return new_name

    # journal images: names do not embed pks, nothing to remap
    # XSL files: journals/<old_pk>/<name> -> journals/<new_pk>/<name>.
    # (matched global XSL files may have journal=None or a name without a
    # journal directory, so match on the embedded old pk)
    old_journal_pk = data["journal"]["pk"]
    old_prefix = "journals/{}/".format(old_journal_pk)
    for xsl in core_models.XSLFile.objects.filter(journal=journal):
        name = xsl.file.name
        if not name or old_prefix not in name:
            continue
        base = os.path.basename(name)
        new_name = "journals/{}/{}".format(journal.pk, base)
        if new_name != name:
            old_path = os.path.join(_base_files_dir(), "xsl", name)
            new_path = os.path.join(_base_files_dir(), "xsl", new_name)
            if os.path.isfile(old_path) and not os.path.exists(new_path):
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(old_path, new_path)
        xsl.file.name = new_name
        xsl.save()
        log("  remapped XSL file to {}".format(new_name))

    # cms media files: media/journals/<old_pk>/<name> (or any name that
    # embeds the old journal pk as first path component)
    for media_file in cms_models.MediaFile.objects.filter(journal=journal):
        name = media_file.file.name
        if not name:
            continue
        parts = name.split("/")
        if len(parts) > 1 and parts[0] in ("journals", "issues", "articles") and parts[1] == str(old_journal_pk):
            base = os.path.basename(name)
            new_name = "journals/{}/{}".format(journal.pk, base)
            if new_name != name:
                old_path = os.path.join(_media_root(), name)
                if os.path.isfile(old_path):
                    new_path = os.path.join(_media_root(), new_name)
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    shutil.move(old_path, new_path)
                media_file.file.name = new_name
                media_file.save()

    # issue images: media/issues/<old_issue_pk>/<name>
    for old_issue_pk, issue_obj in issues.items():
        for field_name in ("large_image", "cover_image"):
            name = _file_name(getattr(issue_obj, field_name, None))
            if not name:
                continue
            base = os.path.basename(name)
            if field_name == "large_image":
                new_name = "issues/{}/{}".format(issue_obj.pk, base)
            else:
                new_name = os.path.join("cover_images", base)
            if new_name != name:
                old_path = os.path.join(_media_root(), name)
                if os.path.isfile(old_path):
                    new_path = os.path.join(_media_root(), new_name)
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    shutil.move(old_path, new_path)
                setattr(issue_obj, field_name, new_name)
                issue_obj.save()

    # article meta images: media/articles/<old_article_pk>/<name>
    for old_article_pk, article_obj in articles.items():
        name = _file_name(article_obj.meta_image)
        if not name:
            continue
        base = os.path.basename(name)
        new_name = "articles/{}/{}".format(article_obj.pk, base)
        if new_name != name:
            old_path = os.path.join(_media_root(), name)
            if os.path.isfile(old_path):
                new_path = os.path.join(_media_root(), new_name)
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(old_path, new_path)
            article_obj.meta_image = new_name
            article_obj.save()


def _import_binary_entry(entry, files_root, ctx, log):
    """Copy one binary out of the bundle to its target location."""
    rel = entry.get("rel")
    kind = entry.get("kind")
    if not rel or not kind:
        return
    src = os.path.join(files_root, rel)
    if not os.path.isfile(src):
        log("  warning: binary missing from bundle: {}".format(rel))
        return

    base_files = _base_files_dir()
    media = _media_root()

    if kind == "article_file":
        article_id = ctx["articles"].get(entry.get("article_id"), None)
        if article_id is None:
            return
        file_obj = ctx["files"].get(entry.get("file_id"))
        if file_obj is None:
            return
        dest = os.path.join(
            base_files, "articles", str(article_id.pk), file_obj.uuid_filename
        )
        _copy_from_bundle(rel, files_root, dest)

    elif kind == "article_file_sub":
        article = ctx["articles"].get(entry.get("article_id"))
        if article is None:
            return
        subpath = entry.get("subpath") or ""
        base = os.path.basename(rel)
        dest = os.path.join(
            base_files, "articles", str(article.pk), subpath, base
        )
        _copy_from_bundle(rel, files_root, dest)

    elif kind == "journal_file":
        file_obj = ctx["files"].get(entry.get("file_id"))
        if file_obj is None:
            return
        dest = os.path.join(
            base_files, "journals", str(ctx["journal"].pk), file_obj.uuid_filename
        )
        _copy_from_bundle(rel, files_root, dest)

    elif kind == "cms_media":
        name = entry.get("name")
        if name:
            dest = os.path.join(media, name)
            _copy_from_bundle(rel, files_root, dest)

    elif kind == "issue_galley_file":
        issue = ctx["issues"].get(entry.get("issue_id"))
        file_obj = ctx["files"].get(entry.get("file_id"))
        if issue is None or file_obj is None:
            return
        dest = os.path.join(
            base_files, "issues", str(issue.pk), file_obj.uuid_filename
        )
        _copy_from_bundle(rel, files_root, dest)

    elif kind == "profile_image":
        account = core_models.Account.objects.filter(
            pk=entry.get("account_id")
        ).first()
        if account is None or not account.profile_image:
            return
        dest = os.path.join(media, account.profile_image.name)
        _copy_from_bundle(rel, files_root, dest)

    elif kind == "xsl":
        dest = os.path.join(base_files, "xsl", entry.get("name", rel))
        _copy_from_bundle(rel, files_root, dest)

    elif kind == "media":
        target = entry.get("target", "")
        if target.startswith("journal."):
            field_name = target.split(".", 1)[1]
            value = _file_name(getattr(ctx["journal"], field_name, None))
            if value:
                dest = os.path.join(media, value)
                _copy_from_bundle(rel, files_root, dest)
        elif target.startswith("issue."):
            issue = ctx["issues"].get(entry.get("issue_id"))
            if issue:
                field_name = target.split(".", 1)[1]
                value = _file_name(getattr(issue, field_name, None))
                if value:
                    dest = os.path.join(media, value)
                    _copy_from_bundle(rel, files_root, dest)
        elif target.startswith("article."):
            article = ctx["articles"].get(entry.get("article_id"))
            if article:
                field_name = target.split(".", 1)[1]
                value = _file_name(getattr(article, field_name, None))
                if value:
                    dest = os.path.join(media, value)
                    _copy_from_bundle(rel, files_root, dest)


def _import_journal_settings(data, journal, log):
    """Create the journal's SettingValue rows from the exported values."""
    settings_count = 0
    _set_rows = data.get("settings", [])
    for _set_idx, entry in enumerate(_set_rows, 1):
        if _set_rows and _set_idx % 100 == 0:
            log("    settings: {}/{}".format(_set_idx, len(_set_rows)))
        try:
            setting = core_models.Setting.objects.get(
                name=entry["name"], group__name=entry["group"]
            )
        except core_models.Setting.DoesNotExist:
            log(
                "  warning: unknown setting {}/{}".format(
                    entry["group"], entry["name"]
                )
            )
            continue
        try:
            setting_value = core_models.SettingValue.objects.get(
                setting=setting, journal=journal
            )
        except core_models.SettingValue.DoesNotExist:
            setting_value = core_models.SettingValue(
                setting=setting, journal=journal
            )
        value = entry.get("value")
        if value is not None:
            setting_value.value = value
        translations = entry.get("_translations") or {}
        for lang, value in translations.items():
            attr = "value_{}".format(lang)
            if hasattr(setting_value, attr):
                setattr(setting_value, attr, value)
        try:
            setting_value.save()
            settings_count += 1
        except Exception as exc:
            log(
                "  warning: could not save setting {}/{}: {}".format(
                    entry["group"], entry["name"], exc
                )
            )
    if settings_count:
        log("  imported settings: {}".format(settings_count))


def _finalize_journal(data, journal, files_map, issues, log):
    """Set journal FKs whose targets only exist after the main import pass."""
    values = data["journal"].get("fields") or {}

    # xsl: XSL files are matched by (globally unique) label, because the
    # imported row may share the global default that update_xsl_files made
    xsl_ref = values.get("xsl_id")
    if xsl_ref:
        label = None
        for row in _rows(data, "xsl_files"):
            if row.get("pk") == xsl_ref:
                label = (row.get("fields") or {}).get("label")
                break
        if label:
            xsl_obj = core_models.XSLFile.objects.filter(label=label).first()
            if xsl_obj is not None:
                journal.xsl = xsl_obj

    # current issue
    current_ref = values.get("current_issue_id")
    if current_ref and current_ref in issues:
        journal.current_issue = issues[current_ref]

    # thumbnail_image is an FK to core.File
    thumb_ref = values.get("thumbnail_image_id")
    if thumb_ref and thumb_ref in files_map:
        journal.thumbnail_image = files_map[thumb_ref]

    journal.save()
