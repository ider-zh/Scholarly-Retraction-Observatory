import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from disruption.status import summarize


class StatusTests(unittest.TestCase):
    def test_completed_run_uses_final_analytical_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / 'full-runs' / 'run'
            (run / 'annual').mkdir(parents=True)
            (run / 'analytical').mkdir()
            (run / 'state.json').write_text(json.dumps({
                'status': 'complete', 'stage': 'all_statistics_cached', 'updated_at': 'test'}))
            (run / 'annual/progress.json').write_text(json.dumps({'completed_partitions': 2}))
            (run / 'analytical/progress.json').write_text(json.dumps({
                'status': 'complete', 'completed_partitions': 3}))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                summarize(root / 'foundation')
            result = json.loads(output.getvalue())
            self.assertEqual(result['progress']['completed_partitions'], 3)
            self.assertEqual(result['progress']['status'], 'complete')
