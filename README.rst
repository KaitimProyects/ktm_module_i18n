================
KTM Module i18n
================

What it provides
=================

Syncs per-language content into three ``ir.module.module`` fields — ``shortdesc``
(Apps title), ``summary`` (Apps subtitle), and ``description`` (Apps body) — for
any installed module, on every registry build. A module opts in simply by
shipping an ``i18n_readme/<lang_code>/`` directory per language it wants to
translate (for example ``i18n_readme/es_MX/``), with up to three independently
optional files inside it: ``name.txt`` -> ``shortdesc``, ``summary.txt`` ->
``summary``, ``description.rst`` -> ``description``. No data files, no manual
step, and no dependency on ``.po`` translation of these fields, which cannot be
corrected once ``base.module_<name>`` has been loaded (see *Gotchas* below).

Why it exists
=============

Odoo's Apps page renders a module's title, subtitle, and description from the
manifest/README at install/update time. Translating those with a plain ``.po``
file works once, but a *corrective* second load is silently ignored: the
``ir.module.module`` record for a third-party module is ``noupdate="1"``, and
only Odoo (owner of ``base``) can refresh it. This module sidesteps that dead
end entirely with a plain ORM ``write()``, which is never subject to
``noupdate``.

Configuration
=============

Nothing to configure. Any module that wants translated Apps-page title,
subtitle, and/or description adds this module to its own ``depends`` (see
*Gotchas*) and ships ``i18n_readme/<lang_code>/{name.txt,summary.txt,
description.rst}`` files next to its own ``README``/manifest. Each file is
independently optional: shipping only ``summary.txt`` translates just the
subtitle for that language, leaving title and description in the source
language.

Gotchas and maintenance notes
==============================

- **Add this module to ``depends``.** The hook is global — it works for any
  installed module regardless of dependency — but without the ``depends``
  edge, a consumer module deployed to a database that lacks this infra module
  degrades silently: no translation, no error.
- **``name.txt`` maps to ``shortdesc``, never to the technical ``name``.**
  ``shortdesc`` is the module's *display* title (and is also ``_rec_name`` —
  it feeds ``display_name`` and technical-name search). The immutable
  technical identifier (``ir.module.module.name``) is never read, written, or
  translated by this module under any circumstance.
- **Never hardcode a language code.** Languages are discovered from active
  ``res.lang`` records in the database (excluding ``en_US``, the source
  language). A hardcoded variant (``es_419`` instead of the DB's real
  ``es_MX``) fails silently.
- **Writes are idempotent, per field.** No ``write()`` is issued for a
  field/language pair whose target already matches the file content, so a
  restart with unchanged files is a no-op; each of the three fields is
  checked and written independently.
- **``shortdesc``/``summary`` are stripped; ``description`` is raw.** A
  trailing newline in a ``char`` field is a real defect (it renders as
  ``display_name``); ``description`` keeps its content verbatim for
  ``docutils`` rendering via ``_get_desc()``, which this module never
  overrides.
- **A blank file is treated as absent**, not as "translate to empty" — a
  stray whitespace-only ``name.txt`` never blanks an already-translated
  title.
- **No warning noise.** Reading falls back cleanly (``None``) for any module
  that has no ``i18n_readme/<lang>/<file>``, via ``tools.file_open`` wrapped
  in ``try/except FileNotFoundError`` — never
  ``get_resource_path``/``get_module_resource``, which fire a
  ``DeprecationWarning`` per call.
