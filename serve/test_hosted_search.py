"""Anthropic hosted search must fail honestly rather than return fake empty results."""
import http.client
import json
from pathlib import Path
import unittest
from unittest import mock

from serve.frontend import ChatTemplate
from serve.server import ByteTokenizer, MockEngine, Service, serve


class HostedSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tok = ByteTokenizer()
        cls.engine = MockEngine(tok, 'ok', max_context=32768)
        cls.svc = Service(cls.engine, tok, ChatTemplate(Path(__file__).with_name('chat_template.jinja')))
        cls.httpd = serve(cls.svc, port=0)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, tool, stream=False):
        c = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        try:
            c.request('POST', '/v1/messages', json.dumps({
                'messages': [{'role': 'user', 'content': 'test'}], 'max_tokens': 8,
                'tools': [tool], 'stream': stream,
            }), {'Content-Type': 'application/json'})
            r = c.getresponse()
            return r.status, r.getheader('Content-Type'), json.loads(r.read())
        finally:
            c.close()

    def test_hosted_search_rejected_before_model_load_or_sse(self):
        for kind in ['web_search_20250305', 'web_search_20260209']:
            for stream in [False, True]:
                with self.subTest(kind=kind, stream=stream), mock.patch.object(self.svc, 'load') as load, \
                        mock.patch.object(self.engine, 'generate') as generate:
                    status, content_type, body = self.post({'type': kind, 'name': 'web_search'}, stream)
                    self.assertEqual(status, 400)
                    self.assertIn('application/json', content_type)
                    self.assertEqual(body['error']['type'], 'invalid_request_error')
                    self.assertIn('No web search was performed', body['error']['message'])
                    load.assert_not_called()
                    generate.assert_not_called()

    def test_user_defined_search_function_is_not_rejected(self):
        status, _, body = self.post({'name': 'web_search', 'description': 'Client search function',
                                    'input_schema': {'type': 'object', 'properties': {}}})
        self.assertEqual(status, 200, body)


if __name__ == '__main__':
    unittest.main()
