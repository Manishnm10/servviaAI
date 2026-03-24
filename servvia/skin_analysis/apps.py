import os
import threading
from django.apps import AppConfig


class SkinAnalysisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "skin_analysis"

    def ready(self):
        # Django runserver spawns two processes (reloader + server).
        # RUN_MAIN is set only in the actual server process — skip the reloader.
        if os.environ.get("RUN_MAIN") != "true":
            return

        # Pre-load the vision model into memory in the background so the
        # first patient request doesn't hit a cold-start delay.
        def _warmup():
            try:
                from edge.skin_classifier import warmup_vision_model
                warmup_vision_model()
            except Exception:
                pass

        threading.Thread(target=_warmup, daemon=True).start()

