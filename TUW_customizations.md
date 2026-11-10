# TUW customisations — `tuw_1.8.4` vs upstream `r-v1.8.x`

This document lists every file that differs between the `tuw_1.8.4` branch and the upstream `r-v1.8.x` branch, grouped into feature areas with a short description of each change. Where the purpose of a change could not be determined with certainty, a placeholder is inserted.

**Scope:** 738 files changed: 644 added, 92 modified, 2 deleted (from `92 M / 644 A / 2 D`).

Legend: `A` = Added, `M` = Modified, `D` = Deleted.

---

## TUW Sync (Alma / DataCite / DOI / NZ linkage)

*(20 files)* — New Django app (`tuw_sync`) that synchronises metadata to Alma and DataCite, creates/registers DOIs, and handles NZ (New Zealand?) link-job callbacks. Contains models (DataCite, Alma, BulkJob), a large logic module, admin, URLs, views, tests, and management commands `update_dois` / `update_metadata`. Backed by the `laapy` bindings.

- A `src/templates/tuw_sync/sync_articles.html`
- A `src/tuw_sync/__init__.py`
- A `src/tuw_sync/admin.py`
- A `src/tuw_sync/alma_marc_values.json`
- A `src/tuw_sync/apps.py`
- A `src/tuw_sync/datacite/__init__.py`
- A `src/tuw_sync/datacite/api.json.SAMPLE`
- A `src/tuw_sync/datacite/api.py`
- A `src/tuw_sync/datacite_values.json`
- A `src/tuw_sync/logic.py`
- A `src/tuw_sync/management/commands/__init__.py`
- A `src/tuw_sync/management/commands/update_dois.py`
- A `src/tuw_sync/management/commands/update_metadata.py`
- A `src/tuw_sync/migrations/0001_initial.py`
- A `src/tuw_sync/migrations/0002_bulk_job.py`
- A `src/tuw_sync/migrations/__init__.py`
- A `src/tuw_sync/models.py`
- A `src/tuw_sync/tests.py`
- A `src/tuw_sync/urls.py`
- A `src/tuw_sync/views.py`

## LAAPy Alma library bindings

*(12 files)* — A vendored client library for the TUW library system (Alma / Primo / Aleph-like API). Provides `api.py` (REST API wrapper), `domain.py` (XML domain objects), `marc.py` (MARC-21 parsing), `db.py` and helpers, plus sample config (`api.json.SAMPLE`, `env.sh.SAMPLE`) and a `create.sql` schema.

- A `src/laapy/__init__.py`
- A `src/laapy/api.json.SAMPLE`
- A `src/laapy/api.py`
- A `src/laapy/api_tests.py`
- A `src/laapy/common.py`
- A `src/laapy/create.sql`
- A `src/laapy/db.py`
- A `src/laapy/domain.py`
- A `src/laapy/env.sh.SAMPLE`
- A `src/laapy/marc.py`
- A `src/laapy/tasks_common.py`
- A `src/laapy/tasks_models.py`

## TUW Backcontent plugin

*(11 files)* — New Django app (`tuw_backcontent`) for retrospective (back-content) article creation/ingestion. Provides views to create and manage imported articles, forms, admin, tests and two templates.

- A `src/templates/tuw_backcontent/articles.html`
- A `src/templates/tuw_backcontent/submission.html`
- A `src/tuw_backcontent/__init__.py`
- A `src/tuw_backcontent/admin.py`
- A `src/tuw_backcontent/apps.py`
- A `src/tuw_backcontent/forms.py`
- A `src/tuw_backcontent/migrations/__init__.py`
- A `src/tuw_backcontent/models.py`
- A `src/tuw_backcontent/tests.py`
- A `src/tuw_backcontent/urls.py`
- A `src/tuw_backcontent/views.py`

## OAI-PMH custom endpoint & serializers

*(13 files)* — Replaces the default OAI endpoint with a TUW-specific `oai_tuw` view and custom OAI XML templates; adds serializers/URL wiring in the Django REST API, plus a `oai` template tag and a `callback_link_nz_job` webhook endpoint.

- M `src/api/serializers.py`
- M `src/api/urls.py`
- M `src/api/views.py`
- A `src/core/templatetags/oai.py`
- A `src/templates/common/apis/oai_tuw/OAI_Error.xml`
- A `src/templates/common/apis/oai_tuw/OAI_GetRecord.xml`
- A `src/templates/common/apis/oai_tuw/OAI_Identify.xml`
- A `src/templates/common/apis/oai_tuw/OAI_ListIdentifiers.xml`
- A `src/templates/common/apis/oai_tuw/OAI_ListMetadataFormats.xml`
- A `src/templates/common/apis/oai_tuw/OAI_ListRecords.xml`
- A `src/templates/common/apis/oai_tuw/OAI_ListSets.xml`
- A `src/templates/common/apis/oai_tuw/OAI_base.xml`
- A `src/templates/common/apis/oai_tuw/OAI_record.xml`

## CMS multilingual navigation & pages

*(15 files)* — Extends the CMS `Page` and `NavigationItem` models with language-aware (translatable) fields and adds filtering of nav items by request language. Includes many data migrations (`9000–9008`) and a `subnav` template tag.

- M `src/cms/forms.py`
- M `src/cms/migrations/0003_auto_20210510_1148.py`
- A `src/cms/migrations/0011_TUW_repair_models.py`
- M `src/cms/migrations/0012_navigationitem_for_footer.py`
- A `src/cms/migrations/9000_TUW_navitem_add_language.py`
- A `src/cms/migrations/9001_TUW_page_translatable_1.py`
- A `src/cms/migrations/9002_TUW_page_translatable_2.py`
- A `src/cms/migrations/9003_TUW_page_translatable_3.py`
- A `src/cms/migrations/9004_TUW_page_translatable_4.py`
- A `src/cms/migrations/9005_TUW_navitem_translatable_1.py`
- A `src/cms/migrations/9006_TUW_navitem_translatable_2.py`
- A `src/cms/migrations/9007_TUW_navitem_translatable_3.py`
- A `src/cms/migrations/9008_TUW_navitem_translatable_4.py`
- M `src/cms/models.py`
- A `src/cms/templatetags/subnav.py`

## Identifiers extension (URN / AC / VLID / MMSID)

*(4 files)* — Adds extra identifier types (`urn`, `ac`, `vlid`, `mmsid`) and their validation regexes to the `identifiers` app, plus a migration to seed the new choices.

- M `src/identifiers/forms.py`
- M `src/identifiers/migrations/0007_batch_doi_registration_20220315.py`
- A `src/identifiers/migrations/9000_TUW_identifier_choices.py`
- M `src/identifiers/models.py`

## Journal issue extensions & ordering

*(9 files)* — Adds issue fields (`tuw_year`, `tuw_issue_str`, `tuw_vlid`, an `under_construction_image`), issue-article ordering helpers and extra issue/gallery URLs, with related migrations and view/form changes.

- M `src/journal/forms.py`
- M `src/journal/issue_forms.py`
- M `src/journal/logic.py`
- M `src/journal/migrations/0042_auto_20210310_1453.py`
- A `src/journal/migrations/9000_tuw_add_issue_str_year_vlid.py`
- A `src/journal/migrations/9001_tuw_add_under_construction_image.py`
- M `src/journal/models.py`
- M `src/journal/urls.py`
- M `src/journal/views.py`

## Submission metadata / translation / models

*(25 files)* — Adds/renames submission model fields (e.g. `CitedReference`, `Funder`, language/subtitle fields, `visible` section toggle, `datacite_state`), new translation fields, and a large set of TUW data migrations (`9000–9011`) that deduplicate keywords, migrate custom-to-bleach fields and repair ordering.

- M `src/submission/forms.py`
- M `src/submission/logic.py`
- D `src/submission/migrations/0035_auto_20190627_1331.py`
- M `src/submission/migrations/0038_merge_20190812_1614.py`
- M `src/submission/migrations/0051_hvad_to_modeltranslations.py`
- M `src/submission/migrations/0062_merge_20211011_0906.py`
- M `src/submission/migrations/0081_auto_20240927_1021.py`
- M `src/submission/migrations/0083_article_jats_article_type_override_and_more.py`
- A `src/submission/migrations/9000_tuw_add_visible_to_section.py`
- A `src/submission/migrations/9001_tuw_add_trans_dedicated_fields.py`
- A `src/submission/migrations/9002_tuw_external_sync.py`
- A `src/submission/migrations/9003_tuw_repair_order.py`
- A `src/submission/migrations/9004_tuw_add_lang_to_submission.py`
- A `src/submission/migrations/9005_tuw_clean_double_keywords.py`
- A `src/submission/migrations/9006_tuw_rename_de_fields.py`
- A `src/submission/migrations/9007_tuw_add_cited_references.py`
- A `src/submission/migrations/9008_tuw_custom_to_bleach_fields_and_more.py`
- A `src/submission/migrations/9009_tuw_article_subtitle_en_article_subtitle_de.py`
- A `src/submission/migrations/9010_tuw_set_missing_article_languages.py`
- A `src/submission/migrations/9011_tuw_remove_obsolete_fields.py`
- M `src/submission/models.py`
- M `src/submission/templatetags/encoding.py`
- M `src/submission/translation.py`
- M `src/submission/urls.py`
- M `src/submission/views.py`

## Metrics explicit-IP tracking

*(4 files)* — Adds an explicit IP tracking field to metrics plus a migration (`9000_tuw_add_explicit_ip.py`) and corresponding logic change.

- M `src/metrics/logic.py`
- M `src/metrics/migrations/0009_fix_metrics_galley_type.py`
- A `src/metrics/migrations/9000_tuw_add_explicit_ip.py`
- M `src/metrics/models.py`

## Core: contacts (GND / spam), OAI helper, locales, views

*(22 files)* — Adds GND-ID and spam flags to contacts, an `oai` template tag, extra German/French locale strings, and various core logic/forms/views/urls changes (entry point for the TUW OAI pipeline, contact handling and helper functions).

- M `src/core/context_processors.py`
- M `src/core/files.py`
- M `src/core/forms/forms.py`
- M `src/core/homepage_elements/issue/hooks.py`
- M `src/core/include_urls.py`
- M `src/core/janeway_global_settings.py`
- A `src/core/locales/de/LC_MESSAGES/django.mo`
- M `src/core/locales/de/LC_MESSAGES/django.po`
- M `src/core/locales/fr/LC_MESSAGES/django.po`
- M `src/core/logic.py`
- M `src/core/migrations/0025_fix_bad_journal_urls_in_template.py`
- M `src/core/migrations/0028_fix_bad_email_urls.py`
- M `src/core/migrations/0039_fix_reviewer_url.py`
- M `src/core/migrations/0047_hvad_to_modeltranslations.py`
- M `src/core/migrations/0082_mark_safe_article_title.py`
- M `src/core/migrations/0100_contacts_name_es_contacts_role_es_and_more.py`
- A `src/core/migrations/9000_tuw_add_gndid.py`
- A `src/core/migrations/9001_tuw_contact_detected_language_contact_is_spam.py`
- A `src/core/migrations/9002_tuw_emulate_filtered_index.py`
- M `src/core/models.py`
- M `src/core/urls.py`
- M `src/core/views.py`

## Press / Repository / Production tweaks

*(4 files)* — Small customisations to Press, Repository and Production models/forms (mostly placeholder – unverified detail trade-off).

- M `src/press/models.py`
- M `src/press/templatetags/press_url.py`
- M `src/production/forms.py`
- M `src/repository/models.py`

## Utils: management commands & journal export/import

*(20 files)* — Adds many TUW management commands (`tuw_export_journal`, `tuw_import_journal`, `tuw_create_account_from_frozen_author`, and a series of `zzz_*` utilities) and the journal export/import helper module `tuw_journal_export.py`.

- M `src/utils/forms.py`
- M `src/utils/install/journal_defaults.json`
- M `src/utils/logic.py`
- M `src/utils/management/commands/import_content.py`
- A `src/utils/management/commands/tuw_create_account_from_frozen_author.py`
- A `src/utils/management/commands/tuw_export_journal.py`
- A `src/utils/management/commands/tuw_import_journal.py`
- A `src/utils/management/commands/zzz_cleanup_titles.py`
- A `src/utils/management/commands/zzz_clone_article.py`
- A `src/utils/management/commands/zzz_create_portfolios.py`
- A `src/utils/management/commands/zzz_delete_account.py`
- A `src/utils/management/commands/zzz_delete_user.py`
- A `src/utils/management/commands/zzz_import_accounts_from_excel.py`
- A `src/utils/management/commands/zzz_import_gndids.py`
- A `src/utils/management/commands/zzz_set_articles_to_unassigned.py`
- A `src/utils/management/commands/zzz_set_missing_settings.py`
- A `src/utils/management/commands/zzz_set_settings_from_file.py`
- A `src/utils/management/commands/zzz_sync_alma.py`
- M `src/utils/notify_plugins/notify_email.py`
- A `src/utils/tuw_journal_export.py`

## Frontend: TUWJFM theme

*(240 files)* — The new `TUWJFM` (Journal für Musik? / TUW journal front-end) theme with its Bootstrap-based assets, Roboto fonts, images, JS and an extensive template set (article, issue, journal, preprints, accounts, press).

- A `src/static/TUWJFM/css/bootstrap.css`
- A `src/static/TUWJFM/css/journal.css`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100italic.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100italic.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100italic.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100italic.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-100italic.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300italic.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300italic.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300italic.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300italic.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-300italic.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500italic.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500italic.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500italic.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500italic.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-500italic.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700italic.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700italic.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700italic.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700italic.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-700italic.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900italic.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900italic.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900italic.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900italic.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-900italic.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-italic.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-italic.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-italic.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-italic.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-italic.woff2`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-regular.eot`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-regular.svg`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-regular.ttf`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-regular.woff`
- A `src/static/TUWJFM/fonts/roboto/roboto-v30-latin-ext_latin-regular.woff2`
- A `src/static/TUWJFM/img/connectors.png`
- A `src/static/TUWJFM/img/favicon_oes.ico`
- A `src/static/TUWJFM/img/janeway_combined_220x28.png`
- A `src/static/TUWJFM/img/janeway_gray_110x28.png`
- A `src/static/TUWJFM/img/janeway_white_110x28.png`
- A `src/static/TUWJFM/img/jfm_logo_150x62.png`
- A `src/static/TUWJFM/img/jfm_title_847x100.png`
- A `src/static/TUWJFM/img/oes_logo_175x62.png`
- A `src/static/TUWJFM/img/oes_title_676x100.png`
- A `src/static/TUWJFM/img/orcid_16x16.png`
- A `src/static/TUWJFM/img/tuw_bib_logo_277x62.png`
- A `src/static/TUWJFM/js/bootstrap.js`
- A `src/themes/TUWJFM/__init__.py`
- A `src/themes/TUWJFM/assets/css/bootstrap-grid.css`
- A `src/themes/TUWJFM/assets/css/bootstrap-grid.css.map`
- A `src/themes/TUWJFM/assets/css/bootstrap-grid.min.css`
- A `src/themes/TUWJFM/assets/css/bootstrap-grid.min.css.map`
- A `src/themes/TUWJFM/assets/css/bootstrap-reboot.css`
- A `src/themes/TUWJFM/assets/css/bootstrap-reboot.css.map`
- A `src/themes/TUWJFM/assets/css/bootstrap-reboot.min.css`
- A `src/themes/TUWJFM/assets/css/bootstrap-reboot.min.css.map`
- A `src/themes/TUWJFM/assets/css/bootstrap.css`
- A `src/themes/TUWJFM/assets/css/bootstrap.css.map`
- A `src/themes/TUWJFM/assets/css/bootstrap.min.css`
- A `src/themes/TUWJFM/assets/css/bootstrap.min.css.map`
- A `src/themes/TUWJFM/assets/css/journal.css`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100italic.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100italic.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100italic.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100italic.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-100italic.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300italic.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300italic.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300italic.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300italic.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-300italic.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500italic.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500italic.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500italic.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500italic.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-500italic.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700italic.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700italic.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700italic.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700italic.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-700italic.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900italic.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900italic.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900italic.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900italic.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-900italic.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-italic.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-italic.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-italic.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-italic.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-italic.woff2`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-regular.eot`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-regular.svg`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-regular.ttf`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-regular.woff`
- A `src/themes/TUWJFM/assets/fonts/roboto/roboto-v30-latin-ext_latin-regular.woff2`
- A `src/themes/TUWJFM/assets/img/connectors.png`
- A `src/themes/TUWJFM/assets/img/favicon.ico`
- A `src/themes/TUWJFM/assets/img/favicon_oes.ico`
- A `src/themes/TUWJFM/assets/img/janeway_combined_220x28.png`
- A `src/themes/TUWJFM/assets/img/janeway_gray_110x28.png`
- A `src/themes/TUWJFM/assets/img/janeway_white_110x28.png`
- A `src/themes/TUWJFM/assets/img/jfm_logo_150x62.png`
- A `src/themes/TUWJFM/assets/img/jfm_title_847x100.png`
- A `src/themes/TUWJFM/assets/img/oes_logo_175x62.png`
- A `src/themes/TUWJFM/assets/img/oes_title_676x100.png`
- A `src/themes/TUWJFM/assets/img/orcid_16x16.png`
- A `src/themes/TUWJFM/assets/img/tuw_bib_logo_277x62.png`
- A `src/themes/TUWJFM/assets/js/bootstrap.js`
- A `src/themes/TUWJFM/assets/js/bootstrap.min.js`
- A `src/themes/TUWJFM/build_assets.py`
- A `src/themes/TUWJFM/templates/403.html`
- A `src/themes/TUWJFM/templates/404.html`
- A `src/themes/TUWJFM/templates/500.html`
- A `src/themes/TUWJFM/templates/cms/page.html`
- A `src/themes/TUWJFM/templates/core/accounts/activate_account.html`
- A `src/themes/TUWJFM/templates/core/accounts/edit_profile.html`
- A `src/themes/TUWJFM/templates/core/accounts/get_reset_token.html`
- A `src/themes/TUWJFM/templates/core/accounts/orcid_registration.html`
- A `src/themes/TUWJFM/templates/core/accounts/public_profile.html`
- A `src/themes/TUWJFM/templates/core/accounts/register.html`
- A `src/themes/TUWJFM/templates/core/accounts/reset_password.html`
- A `src/themes/TUWJFM/templates/core/base.html`
- A `src/themes/TUWJFM/templates/core/login.html`
- A `src/themes/TUWJFM/templates/core/nav.html`
- A `src/themes/TUWJFM/templates/core/news/index.html`
- A `src/themes/TUWJFM/templates/core/news/item.html`
- A `src/themes/TUWJFM/templates/elements/accounts/user_form.html`
- A `src/themes/TUWJFM/templates/elements/article_listing.html`
- A `src/themes/TUWJFM/templates/elements/journal/authors_block.html`
- A `src/themes/TUWJFM/templates/elements/journal/citation_modals.html`
- A `src/themes/TUWJFM/templates/elements/journal/editorial_social_content.html`
- A `src/themes/TUWJFM/templates/elements/journal/how_to_cite.html`
- A `src/themes/TUWJFM/templates/elements/journal/issue_sidebar.html`
- A `src/themes/TUWJFM/templates/elements/journal/issue_top.html`
- A `src/themes/TUWJFM/templates/elements/journal/social_meta.html`
- A `src/themes/TUWJFM/templates/elements/journal/summary_modal.html`
- A `src/themes/TUWJFM/templates/elements/journal_footer.html`
- A `src/themes/TUWJFM/templates/elements/license_block.html`
- A `src/themes/TUWJFM/templates/elements/nav_element.html`
- A `src/themes/TUWJFM/templates/elements/open_modal.html`
- A `src/themes/TUWJFM/templates/elements/preprint_block.html`
- A `src/themes/TUWJFM/templates/elements/press_footer.html`
- A `src/themes/TUWJFM/templates/elements/submit/author.html`
- A `src/themes/TUWJFM/templates/elements/submit/file.html`
- A `src/themes/TUWJFM/templates/elements/submit/preprint_file.html`
- A `src/themes/TUWJFM/templates/elements/submit/timeline.html`
- A `src/themes/TUWJFM/templates/identifiers/crossref.xml`
- A `src/themes/TUWJFM/templates/identifiers/crossref_component.xml`
- A `src/themes/TUWJFM/templates/journal/article.html`
- A `src/themes/TUWJFM/templates/journal/articles.html`
- A `src/themes/TUWJFM/templates/journal/authors.html`
- A `src/themes/TUWJFM/templates/journal/become_reviewer.html`
- A `src/themes/TUWJFM/templates/journal/collections.html`
- A `src/themes/TUWJFM/templates/journal/contact.html`
- A `src/themes/TUWJFM/templates/journal/editorial_team.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/about.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/carousel.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/featured.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/html_block.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/issue_block.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/journals.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/news.html`
- A `src/themes/TUWJFM/templates/journal/homepage_elements/preprints.html`
- A `src/themes/TUWJFM/templates/journal/index.html`
- A `src/themes/TUWJFM/templates/journal/issue.html`
- A `src/themes/TUWJFM/templates/journal/issue_display.html`
- A `src/themes/TUWJFM/templates/journal/issues.html`
- A `src/themes/TUWJFM/templates/journal/newsletter.html`
- A `src/themes/TUWJFM/templates/journal/print.html`
- A `src/themes/TUWJFM/templates/journal/search.html`
- A `src/themes/TUWJFM/templates/journal/submissions.html`
- A `src/themes/TUWJFM/templates/preprints/about.html`
- A `src/themes/TUWJFM/templates/preprints/article.html`
- A `src/themes/TUWJFM/templates/preprints/authors.html`
- A `src/themes/TUWJFM/templates/preprints/editors.html`
- A `src/themes/TUWJFM/templates/preprints/home.html`
- A `src/themes/TUWJFM/templates/preprints/list.html`
- A `src/themes/TUWJFM/templates/preprints/pdf.html`
- A `src/themes/TUWJFM/templates/preprints/review.html`
- A `src/themes/TUWJFM/templates/preprints/search.html`
- A `src/themes/TUWJFM/templates/preprints/submit_files.html`
- A `src/themes/TUWJFM/templates/preprints/submit_start.html`
- A `src/themes/TUWJFM/templates/press/cms/page.html`
- A `src/themes/TUWJFM/templates/press/core/news/index.html`
- A `src/themes/TUWJFM/templates/press/core/news/item.html`
- A `src/themes/TUWJFM/templates/press/nav.html`
- A `src/themes/TUWJFM/templates/press/press_index.html`

## Frontend: TUW_ARW theme & shared static assets

*(294 files)* — The new `TUW_ARW` theme (Foundation-based) with font-awesome, motion-ui, what-input, JS and SCSS assets, plus shared static images/fonts used across TUW themes (Roboto, Merriweather, Montserrat, TU logos).

- A `src/static/common/css/toastr-2.1.1.css`
- A `src/static/common/fonts/merriweather_cyrillic.woff2`
- A `src/static/common/fonts/merriweather_cyrillic_ext.woff2`
- A `src/static/common/fonts/merriweather_latin.woff2`
- A `src/static/common/fonts/merriweather_latin_ext.woff2`
- A `src/static/common/fonts/merriweather_vietnamese.woff2`
- A `src/static/common/fonts/montserrat_cyrillic.woff2`
- A `src/static/common/fonts/montserrat_cyrillic_ext.woff2`
- A `src/static/common/fonts/montserrat_latin.woff2`
- A `src/static/common/fonts/montserrat_latin_ext.woff2`
- A `src/static/common/fonts/montserrat_vietnames.woff2`
- A `src/static/common/img/TU_Signet_blau.svg`
- A `src/static/common/img/TU_Wien_Bibliothek_RGB.svg`
- A `src/static/common/img/favicon-tu.ico`
- A `src/static/common/img/icons/gnd.svg`
- A `src/static/common/img/icons/lobid.png`
- A `src/static/common/js/altcha.min.js`
- A `src/static/common/js/bootstrap.js`
- M `src/static/common/js/tagit.js`
- A `src/static/common/js/toastr-2.1.1.js`
- A `src/static/oes/OeS-PS_Author_Information_2020.pdf`
- A `src/themes/TUW_ARW/README.md`
- A `src/themes/TUW_ARW/__init__.py`
- A `src/themes/TUW_ARW/assets/README.md`
- A `src/themes/TUW_ARW/assets/font-awesome/.bower.json`
- A `src/themes/TUW_ARW/assets/font-awesome/.gitignore`
- A `src/themes/TUW_ARW/assets/font-awesome/.npmignore`
- A `src/themes/TUW_ARW/assets/font-awesome/HELP-US-OUT.txt`
- A `src/themes/TUW_ARW/assets/font-awesome/bower.json`
- A `src/themes/TUW_ARW/assets/font-awesome/css/font-awesome.css`
- A `src/themes/TUW_ARW/assets/font-awesome/css/font-awesome.css.map`
- A `src/themes/TUW_ARW/assets/font-awesome/css/font-awesome.min.css`
- A `src/themes/TUW_ARW/assets/font-awesome/fonts/FontAwesome.otf`
- A `src/themes/TUW_ARW/assets/font-awesome/fonts/fontawesome-webfont.eot`
- A `src/themes/TUW_ARW/assets/font-awesome/fonts/fontawesome-webfont.svg`
- A `src/themes/TUW_ARW/assets/font-awesome/fonts/fontawesome-webfont.ttf`
- A `src/themes/TUW_ARW/assets/font-awesome/fonts/fontawesome-webfont.woff`
- A `src/themes/TUW_ARW/assets/font-awesome/fonts/fontawesome-webfont.woff2`
- A `src/themes/TUW_ARW/assets/font-awesome/less/animated.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/bordered-pulled.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/core.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/fixed-width.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/font-awesome.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/icons.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/larger.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/list.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/mixins.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/path.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/rotated-flipped.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/screen-reader.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/stacked.less`
- A `src/themes/TUW_ARW/assets/font-awesome/less/variables.less`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_animated.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_bordered-pulled.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_core.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_fixed-width.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_icons.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_larger.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_list.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_mixins.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_path.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_rotated-flipped.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_screen-reader.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_stacked.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/_variables.scss`
- A `src/themes/TUW_ARW/assets/font-awesome/scss/font-awesome.scss`
- A `src/themes/TUW_ARW/assets/fonts/FontAwesome.otf`
- A `src/themes/TUW_ARW/assets/fonts/fontawesome-webfont.eot`
- A `src/themes/TUW_ARW/assets/fonts/fontawesome-webfont.svg`
- A `src/themes/TUW_ARW/assets/fonts/fontawesome-webfont.ttf`
- A `src/themes/TUW_ARW/assets/fonts/fontawesome-webfont.woff`
- A `src/themes/TUW_ARW/assets/fonts/fontawesome-webfont.woff2`
- A `src/themes/TUW_ARW/assets/foundation-sites/.github/ISSUE_TEMPLATE.md`
- A `src/themes/TUW_ARW/assets/foundation-sites/.github/PULL_REQUEST_TEMPLATE.md`
- A `src/themes/TUW_ARW/assets/foundation-sites/assets/foundation-flex.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/assets/foundation-rtl.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/assets/foundation.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/customizer/complete.json`
- A `src/themes/TUW_ARW/assets/foundation-sites/customizer/config.yml`
- A `src/themes/TUW_ARW/assets/foundation-sites/customizer/essential.json`
- A `src/themes/TUW_ARW/assets/foundation-sites/customizer/index.html`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.abide.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.accordion.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.accordionMenu.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.core.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.drilldown.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.dropdown.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.dropdownMenu.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.equalizer.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.interchange.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.magellan.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.offcanvas.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.orbit.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.responsiveMenu.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.responsiveToggle.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.reveal.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.slider.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.sticky.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.tabs.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.toggler.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.tooltip.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.box.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.keyboard.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.mediaQuery.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.motion.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.nest.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.timerAndImageLoader.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.touch.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/js/foundation.util.triggers.js`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/_global.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_accordion-menu.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_accordion.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_badge.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_breadcrumbs.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_button-group.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_button.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_callout.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_close-button.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_drilldown.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_dropdown-menu.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_dropdown.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_flex-video.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_flex.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_float.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_label.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_media-object.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_menu-icon.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_menu.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_off-canvas.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_orbit.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_pagination.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_progress-bar.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_reveal.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_slider.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_sticky.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_switch.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_table.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_tabs.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_thumbnail.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_title-bar.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_tooltip.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_top-bar.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/components/_visibility.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_checkbox.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_error.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_fieldset.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_forms.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_help-text.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_input-group.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_label.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_meter.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_progress.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_range.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_select.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/forms/_text.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/foundation.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_classes.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_column.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_flex-grid.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_grid.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_gutter.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_layout.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_position.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_row.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/grid/_size.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/settings/_settings.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/typography/_alignment.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/typography/_base.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/typography/_helpers.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/typography/_print.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/typography/_typography.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_breakpoint.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_color.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_flex.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_mixins.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_selector.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_unit.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_util.scss`
- A `src/themes/TUW_ARW/assets/foundation-sites/scss/util/_value.scss`
- A `src/themes/TUW_ARW/assets/img/TU_Wien_Bibliothek_RGB.svg`
- A `src/themes/TUW_ARW/assets/img/default_carousel/carousel1.png`
- A `src/themes/TUW_ARW/assets/img/default_carousel/carousel2.png`
- A `src/themes/TUW_ARW/assets/img/default_carousel/carousel3.png`
- A `src/themes/TUW_ARW/assets/img/icons/download.png`
- A `src/themes/TUW_ARW/assets/img/icons/users.png`
- A `src/themes/TUW_ARW/assets/img/icons/view.png`
- A `src/themes/TUW_ARW/assets/img/sample/article-small.jpg`
- A `src/themes/TUW_ARW/assets/img/sample/article.jpg`
- A `src/themes/TUW_ARW/assets/jquery/.bower.json`
- A `src/themes/TUW_ARW/assets/js/admin.js`
- A `src/themes/TUW_ARW/assets/js/admin/csrf.js`
- A `src/themes/TUW_ARW/assets/js/admin/modal.js`
- A `src/themes/TUW_ARW/assets/js/admin/proofing_note.js`
- A `src/themes/TUW_ARW/assets/js/admin/tabs.js`
- A `src/themes/TUW_ARW/assets/js/admin/tagit.js`
- A `src/themes/TUW_ARW/assets/js/app.js`
- A `src/themes/TUW_ARW/assets/js/epub.min.js`
- A `src/themes/TUW_ARW/assets/js/footnotes.js`
- A `src/themes/TUW_ARW/assets/js/jq-ui-timepicker.js`
- A `src/themes/TUW_ARW/assets/js/jq-ui.min.js`
- A `src/themes/TUW_ARW/assets/js/jquery-te-1.4.0.min.js`
- A `src/themes/TUW_ARW/assets/js/table_of_contents.js`
- A `src/themes/TUW_ARW/assets/js/text_resize.js`
- A `src/themes/TUW_ARW/assets/js/toastr.js`
- A `src/themes/TUW_ARW/assets/js/zip.min.js`
- A `src/themes/TUW_ARW/assets/motion-ui/.bower.json`
- A `src/themes/TUW_ARW/assets/motion-ui/LICENSE`
- A `src/themes/TUW_ARW/assets/motion-ui/README.md`
- A `src/themes/TUW_ARW/assets/motion-ui/bower.json`
- A `src/themes/TUW_ARW/assets/motion-ui/composer.json`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/animations.md`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/classes.md`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/configuration.md`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/installation.md`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/javascript.md`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/readme.md`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/transitions.md`
- A `src/themes/TUW_ARW/assets/motion-ui/docs/wow.md`
- A `src/themes/TUW_ARW/assets/motion-ui/gulpfile.js`
- A `src/themes/TUW_ARW/assets/motion-ui/motion-ui.js`
- A `src/themes/TUW_ARW/assets/motion-ui/motion-ui.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/package.json`
- A `src/themes/TUW_ARW/assets/motion-ui/src/_classes.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/_settings.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/effects/_fade.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/effects/_hinge.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/effects/_shake.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/effects/_slide.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/effects/_spin.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/effects/_wiggle.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/effects/_zoom.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/motion-ui.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/transitions/_fade.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/transitions/_hinge.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/transitions/_slide.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/transitions/_spin.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/transitions/_zoom.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/util/_animation.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/util/_args.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/util/_keyframe.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/util/_selector.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/util/_series.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/util/_transition.scss`
- A `src/themes/TUW_ARW/assets/motion-ui/src/util/_unit.scss`
- A `src/themes/TUW_ARW/assets/scss/_issue.scss`
- A `src/themes/TUW_ARW/assets/scss/_mixins.scss`
- A `src/themes/TUW_ARW/assets/scss/_settings.scss`
- A `src/themes/TUW_ARW/assets/scss/_tabs.scss`
- A `src/themes/TUW_ARW/assets/scss/_tagit.scss`
- A `src/themes/TUW_ARW/assets/scss/_timeline.scss`
- A `src/themes/TUW_ARW/assets/scss/_toastr.scss`
- A `src/themes/TUW_ARW/assets/scss/_variables.scss`
- A `src/themes/TUW_ARW/assets/scss/admin.css`
- A `src/themes/TUW_ARW/assets/scss/app.css`
- A `src/themes/TUW_ARW/assets/scss/app.scss`
- A `src/themes/TUW_ARW/assets/scss/jq-ui-timepicker.css`
- A `src/themes/TUW_ARW/assets/scss/jq-ui.css`
- A `src/themes/TUW_ARW/assets/scss/jquery-te-1.4.0.css`
- A `src/themes/TUW_ARW/assets/scss/jquery-te.png`
- A `src/themes/TUW_ARW/assets/scss/pdf.css`
- A `src/themes/TUW_ARW/assets/what-input/.bower.json`
- A `src/themes/TUW_ARW/assets/what-input/LICENSE`
- A `src/themes/TUW_ARW/assets/what-input/README.md`
- A `src/themes/TUW_ARW/assets/what-input/bower.json`
- A `src/themes/TUW_ARW/assets/what-input/gulpfile.js/index.js`
- A `src/themes/TUW_ARW/assets/what-input/gulpfile.js/tasks/clean.js`
- A `src/themes/TUW_ARW/assets/what-input/gulpfile.js/tasks/default.js`
- A `src/themes/TUW_ARW/assets/what-input/gulpfile.js/tasks/scripts.js`
- A `src/themes/TUW_ARW/assets/what-input/index.html`
- A `src/themes/TUW_ARW/assets/what-input/lte-IE8.js`
- A `src/themes/TUW_ARW/assets/what-input/package.json`
- A `src/themes/TUW_ARW/assets/what-input/polyfills/ie8/EventListener.js`
- A `src/themes/TUW_ARW/assets/what-input/polyfills/ie8/indexOf.js`
- A `src/themes/TUW_ARW/assets/what-input/what-input.js`
- A `src/themes/TUW_ARW/assets/what-input/what-input.min.js`
- A `src/themes/TUW_ARW/build_assets.py`
- A `src/themes/TUW_ARW/templates/core/accounts/register.html`
- A `src/themes/TUW_ARW/templates/core/base.html`
- A `src/themes/TUW_ARW/templates/core/nav.html`
- A `src/themes/TUW_ARW/templates/core/news/item.html`
- A `src/themes/TUW_ARW/templates/elements/journal/article_filter_form.html`
- A `src/themes/TUW_ARW/templates/elements/journal/article_list_filters.html`
- A `src/themes/TUW_ARW/templates/elements/journal/box_article.html`
- A `src/themes/TUW_ARW/templates/elements/journal/citation_modals.html`
- A `src/themes/TUW_ARW/templates/elements/journal/issue_block.html`
- A `src/themes/TUW_ARW/templates/elements/journal/issue_list.html`
- A `src/themes/TUW_ARW/templates/elements/journal/issue_sidebar.html`
- A `src/themes/TUW_ARW/templates/elements/journal_footer.html`
- A `src/themes/TUW_ARW/templates/journal/article.html`
- A `src/themes/TUW_ARW/templates/journal/article_list.html`
- A `src/themes/TUW_ARW/templates/journal/articles.html`
- A `src/themes/TUW_ARW/templates/journal/issue.html`
- A `src/themes/TUW_ARW/templates/journal/issues.html`
- A `src/themes/TUW_ARW/theme_settings.json`

## Frontend: existing theme tweaks (clean / material / OLH)

*(7 files)* — Small overrides in the built-in Clean, Material and OLH themes (nav and user-form templates).

- M `src/themes/OLH/templates/core/nav.html`
- M `src/themes/OLH/templates/elements/accounts/user_form.html`
- M `src/themes/OLH/templates/elements/journal/box_article.html`
- M `src/themes/clean/templates/core/nav.html`
- M `src/themes/clean/templates/elements/accounts/user_form.html`
- M `src/themes/material/templates/core/nav.html`
- M `src/themes/material/templates/elements/accounts/user_form.html`

## Admin & common template overrides

*(22 files)* — Overrides to Django admin and common templates (base nav, metadata, submit, issue modal, pagination, bibtex, messages, meta tags) to reflect TUW customisations.

- M `src/templates/admin/core/base.html`
- M `src/templates/admin/core/manager/images/article_image.html`
- M `src/templates/admin/core/manager/pinned_articles.html`
- M `src/templates/admin/core/nav.html`
- M `src/templates/admin/elements/article_jump.html`
- M `src/templates/admin/elements/cms_nav.html`
- M `src/templates/admin/elements/current_authors_inner.html`
- M `src/templates/admin/elements/forms/group_journal.html`
- M `src/templates/admin/elements/forms/group_journal_images.html`
- M `src/templates/admin/elements/issue/issue_modal.html`
- M `src/templates/admin/elements/metadata.html`
- M `src/templates/admin/elements/submit/author.html`
- M `src/templates/admin/journal/manage/archive_article.html`
- M `src/templates/admin/journal/manage/issues.html`
- M `src/templates/admin/press/press_manager_index.html`
- M `src/templates/admin/submission/edit/metadata.html`
- M `src/templates/admin/submission/submit_info.html`
- M `src/templates/admin/submission/submit_review.html`
- M `src/templates/common/elements/article_meta_tags.html`
- A `src/templates/common/elements/messages.html`
- M `src/templates/common/elements/pagination.html`
- M `src/templates/common/encoding/article_bibtex.bib`

## tuw_tools helper scripts

*(11 files)* — Operational shell / SQL helper scripts (dev & test environment setup, session/drop-all SQL, webhook link-job handlers).

- A `tuw_tools/compare_dirs_and_delete_identical_files.sh`
- A `tuw_tools/create_django_session.sql`
- A `tuw_tools/delete_expired_sessions.sql`
- A `tuw_tools/dev_environment.sh`
- A `tuw_tools/drop_all_except_session.sh`
- A `tuw_tools/drop_all_except_session_and_execute.sh`
- A `tuw_tools/test_environment.sh`
- A `tuw_tools/webhook_process_link_job/check_webhook`
- A `tuw_tools/webhook_process_link_job/process_janeway_link_job`
- A `tuw_tools/webhook_process_link_job/webhook`
- A `tuw_tools/webhook_process_link_job/webhook.test`

## Infrastructure & dependencies

*(4 files)* — Dependency and repo meta changes: Django upgraded (4.2.22→4.2.28), added TUW deps (pdf2image, freezegun, gunicorn, mysqlclient, mariadb, django-simple-captcha, django-altcha, django-extensions, lingua-language-detector, numpy, openpyxl, xlsxwriter), removed django-recaptcha. Also `.gitattributes` / `.gitignore` tweaks.

- M `.gitattributes`
- M `.gitignore`
- M `dev-requirements.txt`
- M `requirements.txt`

## Removed / misc

*(1 file)* — Removed the `src/texture` directory; no other ungrouped leftovers.

- D `src/texture`

---
