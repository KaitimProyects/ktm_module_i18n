================
KTM Module i18n
================

Que ofrece
==========

Sincroniza contenido por idioma hacia tres campos de ``ir.module.module`` —
``shortdesc`` (titulo en Aplicaciones), ``summary`` (subtitulo en
Aplicaciones) y ``description`` (cuerpo en Aplicaciones) — para cualquier
modulo instalado, en cada construccion del registro. Un modulo se suma
simplemente publicando un directorio ``i18n_metadata/<codigo_idioma>/`` por
cada idioma que quiera traducir (por ejemplo ``i18n_metadata/es_MX/``), con
hasta tres archivos independientemente opcionales adentro: ``name.txt`` ->
``shortdesc``, ``summary.txt`` -> ``summary``, ``description.rst`` ->
``description``. Sin archivos de datos, sin paso manual, y sin depender de
traducir estos campos via ``.po``, lo cual no puede corregirse una vez que
``base.module_<nombre>`` ya fue cargado.

Por que existe
===============

La pagina de Aplicaciones de Odoo renderiza el titulo, subtitulo y
descripcion de un modulo desde el manifiesto/README al instalar o
actualizar. Traducir eso con un archivo ``.po`` funciona una vez, pero una
segunda carga *correctiva* se ignora silenciosamente: el registro
``ir.module.module`` de un modulo de terceros es ``noupdate="1"``, y solo
Odoo (dueño de ``base``) puede refrescarlo. Este modulo evita ese callejon
sin salida con un simple ``write()`` del ORM, que nunca esta sujeto a
``noupdate``.
