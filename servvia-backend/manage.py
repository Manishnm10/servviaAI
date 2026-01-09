#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Windows compatibility fix for pwd module (Unix-only)
if sys.platform == 'win32':
    import types
    sys.modules['pwd'] = types. ModuleType('pwd')
    sys.modules['pwd'].getpwuid = lambda x: None
    sys.modules['grp'] = types.ModuleType('grp')
    sys. modules['grp'].getgrgid = lambda x: None


def main():
    """Run administrative tasks."""
    os.environ. setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()