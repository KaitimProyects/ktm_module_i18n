import os

from odoo import models, tools


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    README_I18N_DIR = 'i18n_readme'

    def _get_readme_translation_fields(self):
        """Map each translatable field to the file that feeds it, under
        `i18n_readme/<lang>/`.

        A method, not a class-attribute dict: a child module can extend the
        mapping with `{**super()._get_readme_translation_fields(), 'x': 'x.txt'}`
        without having to redefine every other seam.

        Filenames mirror manifest keys (`name`, `summary`, `description`), not
        ORM field names — `name.txt` maps to `shortdesc` (the module's
        *display* title) and never to the immutable technical `name`.
        """
        return {
            'shortdesc': 'name.txt',
            'summary': 'summary.txt',
            'description': 'description.rst',
        }

    def _read_readme_translation(self, module_name, lang, filename):
        """Return the content of <module_name>/i18n_readme/<lang>/<filename>,
        or None.

        Uses `tools.file_open` (the non-deprecated API, `env=self.env` so it
        also resolves inside `file_open_temporary_directory` fixtures) instead
        of `get_resource_path`/`get_module_resource`, which fire a
        `DeprecationWarning` per call.

        `filter_ext` is derived from the filename's own extension rather than
        hardcoded, so this seam stays correct for every entry
        `_get_readme_translation_fields()` maps — a hardcoded `('.rst',)`
        would raise `ValueError` from `tools.file_open`/`file_path` the
        moment a `.txt` file (`name.txt`/`summary.txt`) is read.
        """
        relative_path = f'{module_name}/{self.README_I18N_DIR}/{lang}/{filename}'
        ext = os.path.splitext(filename)[1]
        try:
            with tools.file_open(relative_path, 'r', filter_ext=(ext,), env=self.env) as readme_file:
                return readme_file.read()
        except FileNotFoundError:
            return None

    def _normalize_readme_translation(self, field_name, content):
        """Normalize file content before it is compared/written to `field_name`.

        `char` fields (`shortdesc`, `summary`) are stripped: a trailing
        newline is a real defect there — `shortdesc` is `_rec_name`
        (`ir_module.py:162`) and renders as `display_name`. `description`
        (an `html`/`text` field) keeps its raw content untouched.

        A whitespace-only file normalizes to `''`; the caller treats an
        empty-after-strip result as absent, so a stray blank file never
        blanks an already-translated field.
        """
        if self._fields[field_name].type == 'char':
            return content.strip()
        return content

    def _get_readme_translation_langs(self):
        """Active languages to sync into, excluding the source language.

        Derived from `res.lang` records actually active in this database —
        never a hardcoded list. Hardcoding a variant (e.g. `es_419`) silently
        fails the moment the real deployment uses a different one (`es_MX`).
        """
        langs = self.env['res.lang'].search([
            ('active', '=', True),
            ('code', '!=', 'en_US'),
        ])
        return langs.mapped('code')

    def _get_readme_translation_modules(self):
        """Installed modules, candidates for a readme-translation sync."""
        return self.sudo().search([('state', '=', 'installed')])

    def _sync_readme_translations(self):
        """Copy each installed module's i18n_readme/<lang>/<file> content into
        its translated `shortdesc`/`summary`/`description`, one ORM write per
        changed (module, lang) pair.

        Model-level: ignores `self`'s ids and looks at every installed
        module. Langs is the outer loop so `modules.with_context(lang=lang)`
        is hoisted out of the inner loop instead of being recomputed once per
        module. Fields sync independently: a missing/absent file for one
        field just `continue`s for that field only, never blocking its
        siblings; a single `write(vals)` batches every changed field for that
        (module, lang) pair.
        """
        modules = self._get_readme_translation_modules()
        fields = self._get_readme_translation_fields()
        for lang in self._get_readme_translation_langs():
            translated_modules = modules.with_context(lang=lang)
            for module in translated_modules:
                vals = {}
                for field_name, filename in fields.items():
                    content = self._read_readme_translation(module.name, lang, filename)
                    if content is None:
                        continue
                    content = self._normalize_readme_translation(field_name, content)
                    if not content:
                        continue
                    if module[field_name] != content:
                        vals[field_name] = content
                if vals:
                    module.write(vals)

    def _register_hook(self):
        super()._register_hook()
        self._sync_readme_translations()
