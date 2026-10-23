"""Cage tests for the Supabase adapter against the local stand-in."""
import os, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import supabase_adapter as sa


class TestStandIn(unittest.TestCase):
    def test_task_roundtrip(self):
        store = sa.LocalStandIn()
        tid = store.put_task("freecloud-7000", "client-zero", "smoke task")
        self.assertEqual(store.get_task(tid)["status"], "queued")
        store.put_result(tid, "done")
        self.assertEqual(store.get_task(tid)["result"], "done")
        self.assertEqual(store.count("completed"), 1)

    def test_health_ok(self):
        self.assertTrue(sa.LocalStandIn().health()["ok"])

    def test_missing_task_is_none_not_invented(self):
        self.assertIsNone(sa.LocalStandIn().get_task(9999))


class TestSupabaseGate(unittest.TestCase):
    def test_unconfigured_raises_named_error(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE_")}
        old = dict(os.environ)
        try:
            os.environ.clear(); os.environ.update(env)
            with self.assertRaises(sa.NotConfigured):
                sa.SupabaseStore(url="", key="")
        finally:
            os.environ.clear(); os.environ.update(old)

    def test_from_env_falls_back_honestly(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE_")}
        old = dict(os.environ)
        try:
            os.environ.clear(); os.environ.update(env)
            self.assertEqual(sa.from_env().name, "local-standin")
        finally:
            os.environ.clear(); os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
