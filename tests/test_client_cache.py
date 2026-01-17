# Read tests/knowledge.md in this directory for how to run tests.
import unittest
import time
import asyncio

from src.manifold_client import ManifoldClient

class TestClientCache(unittest.TestCase):
    def setUp(self):
        self.client = ManifoldClient(api_key="dummy")
        asyncio.run(self.client.init())
        self.client.cache_ttl = 1
        self.client.cache_ttl_overrides = {}

    def tearDown(self):
        asyncio.run(self.client.close())

    def test_cleanup_cache_removes_expired_entries(self):
        self.client._cache = {
            'old': (time.time() - 5, {'data': 'old'}),
            'new': (time.time(), {'data': 'new'})
        }
        self.client._cleanup_cache()
        self.assertIn('new', self.client._cache)
        self.assertNotIn('old', self.client._cache)

    def test_make_request_triggers_cleanup(self):
        def fake_get(*args, **kwargs):
            class DummyCM:
                status = 200
                async def __aenter__(self_inner):
                    return self_inner
                async def __aexit__(self_inner, exc_type, exc, tb):
                    pass
                async def json(self_inner):
                    return {'result': 'ok'}
            return DummyCM()
        self.client.session.get = fake_get

        cache_key = 'endpoint:'
        self.client._cache[cache_key] = (time.time() - 5, {'data': 'stale'})

        asyncio.run(self.client._make_request('endpoint'))
        self.assertIn(cache_key, self.client._cache)
        self.assertEqual(self.client._cache[cache_key][1], {'result': 'ok'})

    def test_ttl_override_used(self):
        self.client.cache_ttl = 1
        self.client.cache_ttl_overrides = {'endpoint': 5}
        cache_key = 'endpoint:'
        self.client._cache[cache_key] = (time.time() - 3, {'data': 'fresh'})
        # Should still be cached because override TTL is 5 seconds
        self.client._cleanup_cache()
        self.assertIn(cache_key, self.client._cache)
        # After the override TTL expires the entry should be removed
        self.client._cache[cache_key] = (time.time() - 6, {'data': 'stale'})
        self.client._cleanup_cache()
        self.assertNotIn(cache_key, self.client._cache)

if __name__ == '__main__':
    unittest.main()
