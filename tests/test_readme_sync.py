import os
import warnings
from unittest.mock import patch

from odoo.tools import file_open_temporary_directory

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReadmeSync(TransactionCase):

    def test_read_emits_no_deprecation_warning(self):
        """_read_readme_translation must use the non-deprecated file_open API,
        for every mapped filename/extension (.txt and .rst alike).

        `base` ships no `i18n_readme/` directory, so this exercises the
        "module without i18n_readme" path while proving no DeprecationWarning
        escapes (the get_resource_path bug this module fixes), across all
        three extensions the field mapping produces.
        """
        module = self.env['ir.module.module']
        fields = module._get_readme_translation_fields()
        for field_name, filename in fields.items():
            with self.subTest(field=field_name, filename=filename):
                with warnings.catch_warnings():
                    warnings.simplefilter('error', DeprecationWarning)
                    result = module._read_readme_translation('base', 'es_MX', filename)
                self.assertIsNone(result)

    def test_ignores_module_without_readme_dir(self):
        """A module with no i18n_readme/<lang>/<filename> returns None, not an error."""
        module = self.env['ir.module.module']
        result = module._read_readme_translation('web', 'es_MX', 'description.rst')
        self.assertIsNone(result)

    def test_char_fields_are_stripped(self):
        """`char` fields (shortdesc, summary) are stripped; description is raw."""
        module = self.env['ir.module.module']
        self.assertEqual(
            module._normalize_readme_translation('shortdesc', 'Titulo traducido\n'),
            'Titulo traducido',
        )
        self.assertEqual(
            module._normalize_readme_translation('summary', 'Resumen traducido\n'),
            'Resumen traducido',
        )
        raw = 'Descripcion\n\ncon saltos\n'
        self.assertEqual(
            module._normalize_readme_translation('description', raw),
            raw,
        )

    def test_blank_file_is_treated_as_absent(self):
        """A whitespace-only file normalizes to '' — treated as absent by the caller."""
        module = self.env['ir.module.module']
        self.assertEqual(module._normalize_readme_translation('shortdesc', '   \n'), '')

    def test_langs_exclude_en_US_and_inactive(self):
        """Languages come from active res.lang records, never a hardcoded list.

        Regression for the `es_419` gotcha: the DB's real active variant
        (`es_MX`) must be discovered dynamically, `en_US` (the source
        language) must never be treated as a translation target, and an
        inactive language must never be included.
        """
        lang_model = self.env['res.lang'].sudo()
        fr_fr = lang_model.with_context(active_test=False).search([('code', '=', 'fr_FR')])
        if not fr_fr:
            self.skipTest('fr_FR language is not loaded in this database')

        langs_before = self.env['ir.module.module']._get_readme_translation_langs()
        self.assertNotIn('en_US', langs_before)
        self.assertNotIn('fr_FR', langs_before)

        fr_fr.write({'active': True})
        langs_after = self.env['ir.module.module']._get_readme_translation_langs()
        self.assertIn('fr_FR', langs_after)
        self.assertIn('es_MX', langs_after)
        self.assertNotIn('en_US', langs_after)

    def test_writes_all_three_fields_when_present(self):
        """All three files present → all three fields translated for that lang."""
        ir_module_module = type(self.env['ir.module.module'])
        base_module = self.env.ref('base.module_base')
        content = {
            'name.txt': 'Titulo traducido',
            'summary.txt': 'Resumen traducido',
            'description.rst': 'Descripcion traducida',
        }

        def fake_read(self, module_name, lang, filename):
            if module_name == 'base' and lang == 'es_MX':
                return content.get(filename)
            return None

        with patch.object(ir_module_module, '_get_readme_translation_langs', return_value=['es_MX']), \
             patch.object(ir_module_module, '_get_readme_translation_modules', return_value=base_module), \
             patch.object(ir_module_module, '_read_readme_translation', fake_read):
            self.env['ir.module.module']._sync_readme_translations()

        translated = base_module.with_context(lang='es_MX')
        self.assertEqual(translated.shortdesc, content['name.txt'])
        self.assertEqual(translated.summary, content['summary.txt'])
        self.assertEqual(translated.description, content['description.rst'])

    def test_field_independence_partial_files(self):
        """Only summary.txt present → only summary is translated.

        shortdesc and description must stay in the source language for that
        language — a missing file for one field never blocks the others.
        """
        ir_module_module = type(self.env['ir.module.module'])
        base_module = self.env.ref('base.module_base')
        # Baseline captured under the TARGET language, not the source
        # language: `base` ships its own official es_MX translation for
        # `shortdesc`/`description` via the language pack, independent of
        # this module's sync. Comparing against the English source would be
        # wrong — the assertion is "our sync left these two fields alone",
        # not "these two fields are untranslated".
        es_mx_base = base_module.with_context(lang='es_MX')
        shortdesc_before = es_mx_base.shortdesc
        description_before = es_mx_base.description
        summary_content = 'Solo resumen traducido'

        def fake_read(self, module_name, lang, filename):
            if module_name == 'base' and lang == 'es_MX' and filename == 'summary.txt':
                return summary_content
            return None

        with patch.object(ir_module_module, '_get_readme_translation_langs', return_value=['es_MX']), \
             patch.object(ir_module_module, '_get_readme_translation_modules', return_value=base_module), \
             patch.object(ir_module_module, '_read_readme_translation', fake_read):
            self.env['ir.module.module']._sync_readme_translations()

        translated = base_module.with_context(lang='es_MX')
        self.assertEqual(translated.summary, summary_content)
        self.assertEqual(translated.shortdesc, shortdesc_before)
        self.assertEqual(translated.description, description_before)

    def test_single_write_per_module_lang(self):
        """Exactly one write() per (module, lang), carrying all changed fields."""
        ir_module_module = type(self.env['ir.module.module'])
        base_module = self.env.ref('base.module_base')
        content = {
            'name.txt': 'Titulo',
            'summary.txt': 'Resumen',
            'description.rst': 'Descripcion',
        }

        def fake_read(self, module_name, lang, filename):
            if module_name == 'base' and lang == 'es_MX':
                return content.get(filename)
            return None

        with patch.object(ir_module_module, '_get_readme_translation_langs', return_value=['es_MX']), \
             patch.object(ir_module_module, '_get_readme_translation_modules', return_value=base_module), \
             patch.object(ir_module_module, '_read_readme_translation', fake_read), \
             patch.object(ir_module_module, 'write', autospec=True, side_effect=ir_module_module.write) as mocked_write:
            self.env['ir.module.module']._sync_readme_translations()

        mocked_write.assert_called_once()
        vals = mocked_write.call_args.args[1]
        self.assertEqual(set(vals), {'shortdesc', 'summary', 'description'})

    def test_skips_write_when_unchanged(self):
        """A second sync with all three fields unchanged issues zero writes."""
        ir_module_module = type(self.env['ir.module.module'])
        base_module = self.env.ref('base.module_base')
        content = {
            'name.txt': 'Titulo idempotente',
            'summary.txt': 'Resumen idempotente',
            'description.rst': 'Descripcion idempotente',
        }

        def fake_read(self, module_name, lang, filename):
            if module_name == 'base' and lang == 'es_MX':
                return content.get(filename)
            return None

        with patch.object(ir_module_module, '_get_readme_translation_langs', return_value=['es_MX']), \
             patch.object(ir_module_module, '_get_readme_translation_modules', return_value=base_module), \
             patch.object(ir_module_module, '_read_readme_translation', fake_read):
            self.env['ir.module.module']._sync_readme_translations()

            with patch.object(ir_module_module, 'write', autospec=True) as mocked_write:
                self.env['ir.module.module']._sync_readme_translations()

        mocked_write.assert_not_called()

    def test_end_to_end_via_temp_addons_dir(self):
        """Full pipeline: real files on disk, no mocked seams.

        Uses `file_open_temporary_directory` so a real `base/i18n_readme/
        es_MX/{name.txt,summary.txt,description.rst}` can be planted on disk
        without touching the actual `base` module directory, then runs the
        unpatched `_sync_readme_translations` end to end.
        """
        base_module = self.env.ref('base.module_base')
        shortdesc_content = 'Titulo end-to-end'
        summary_content = 'Resumen end-to-end'
        description_content = 'Descripcion end-to-end\n\ncon varias lineas\n'

        with file_open_temporary_directory(self.env) as module_dir:
            readme_dir = os.path.join(module_dir, 'base', 'i18n_readme', 'es_MX')
            os.makedirs(readme_dir)
            with open(os.path.join(readme_dir, 'name.txt'), 'w', encoding='utf-8') as name_file:
                name_file.write(shortdesc_content)
            with open(os.path.join(readme_dir, 'summary.txt'), 'w', encoding='utf-8') as summary_file:
                summary_file.write(summary_content)
            with open(os.path.join(readme_dir, 'description.rst'), 'w', encoding='utf-8') as description_file:
                description_file.write(description_content)

            self.env['ir.module.module']._sync_readme_translations()

        translated = base_module.with_context(lang='es_MX')
        self.assertEqual(translated.shortdesc, shortdesc_content)
        self.assertEqual(translated.summary, summary_content)
        self.assertEqual(translated.description, description_content)

    def test_display_name_and_technical_search_after_shortdesc_translation(self):
        """`shortdesc` is `_rec_name` (ir_module.py:162) and feeds
        `_rec_names_search` (:163) — a wider blast radius than `description`
        ever had. Translating it must (a) show up in `display_name` under
        that language's context, and (b) never break searching by the
        immutable technical `name`.
        """
        ir_module_module = type(self.env['ir.module.module'])
        base_module = self.env.ref('base.module_base')
        translated_title = 'Titulo traducido para display_name'

        def fake_read(self, module_name, lang, filename):
            if module_name == 'base' and lang == 'es_MX' and filename == 'name.txt':
                return translated_title
            return None

        with patch.object(ir_module_module, '_get_readme_translation_langs', return_value=['es_MX']), \
             patch.object(ir_module_module, '_get_readme_translation_modules', return_value=base_module), \
             patch.object(ir_module_module, '_read_readme_translation', fake_read):
            self.env['ir.module.module']._sync_readme_translations()

        self.assertEqual(
            base_module.with_context(lang='es_MX').display_name,
            translated_title,
        )
        found = self.env['ir.module.module'].search([('name', '=', 'base')])
        self.assertEqual(found, base_module)
        self.assertEqual(found.name, 'base')
