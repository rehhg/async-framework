import asyncio

from httptools import HttpRequestParser

from .request import Request
from .response import Response
from .http_parser import HttpParserMixin


class Server(asyncio.Protocol, HttpParserMixin):
    def __init__(self, loop, handler, app):
        self._loop = loop
        self._app = app
        self._encoding = 'utf-8'
        self._url = None
        self._request = None
        self._body = None
        self._request_class = Request
        self._request_handler = handler
        self._request_handler_task = None
        self._transport = None
        self._request_parser = HttpRequestParser(self)
        self._headers = {}

    def connection_made(self, transport):
        self._transport = transport

    def connection_lost(self, *args):
        self._transport = None

    def data_received(self, data):
        self._request_parser.feed_data(data)

        resp = Response(body=f'Received request on {self._request.url}')
        self._transport.write(str(resp).encode(self._encoding))

        self._transport.close()

    def response_writer(self, response):
        self._transport.write(str(response).encode(self._encoding))
        self._transport.close()
