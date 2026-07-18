"""
Compile locale/*.po files to .mo using polib.

Windows-friendly replacement for `manage.py compilemessages`, which requires
the GNU gettext binaries. Usage:

    python manage.py compile_translations
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Compile all locale/**/django.po files to django.mo (no gettext needed)"

    def handle(self, *args, **options):
        try:
            import polib
        except ImportError:
            raise CommandError("polib is required: pip install polib")

        compiled = 0
        for locale_dir in settings.LOCALE_PATHS:
            for po_path in Path(locale_dir).glob("*/LC_MESSAGES/*.po"):
                mo_path = po_path.with_suffix(".mo")
                po = polib.pofile(str(po_path))
                po.save_as_mofile(str(mo_path))
                self.stdout.write(f"Compiled {po_path} -> {mo_path.name} ({len(po)} entries)")
                compiled += 1

        if not compiled:
            self.stdout.write(self.style.WARNING("No .po files found."))
        else:
            self.stdout.write(self.style.SUCCESS(f"{compiled} catalog(s) compiled."))
