import importlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script"))
shared = importlib.import_module("tools._shared")
class AnalysisPersistenceTests(unittest.TestCase):
 def test_proxy_timestamps_map_to_source_timeline(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp); source=root/"source.mp4"; proxy=root/"proxy.mp4"; output=root/"source_analysis.json"; source.touch(); proxy.touch()
   def meta(path): return {"duration_seconds": 120.0 if Path(path)==source else 45.0}
   with patch.object(shared,"_analysis_output_path",return_value=output), patch.object(shared,"_get_video_meta",side_effect=meta): result=shared._save_analysis_json(source,proxy,"test","t=9s-t=15s campus","file://proxy","")
   self.assertEqual(result,output); payload=json.loads(output.read_text(encoding="utf-8")); self.assertEqual(payload["segments"],[{"start":24.0,"end":40.0}]); self.assertEqual([(x["start"],x["end"],x["duration"]) for x in payload["semantic_segments"]],[(24.0,40.0,16.0)]); self.assertAlmostEqual(payload["analysis_to_source_time_scale"],120/45)
if __name__=="__main__": unittest.main()
