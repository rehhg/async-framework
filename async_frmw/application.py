import signal
import asyncio

from functools import partial

from .router import UrlDispatcher
from .server import Server
from .response import Response
from .exceptions import HTTPException
from .helpers import format_exception


class Application:
    def __init__(self, loop=None, middlewares=None):
        self._middlewares = middlewares
        if loop is None:
            loop = asyncio.get_event_loop()
        if middlewares is None:
            self._middlewares = []

        self._loop = loop
        self._router = UrlDispatcher()
        self._on_startup = []
        self._on_shutdown = []

    @property
    def loop(self):
        return self._loop

    @property
    def router(self):
        return self._router

    @property
    def on_startup(self):
        return self._on_startup

    @property
    def on_shutdown(self):
        return self._on_shutdown

    def _make_server(self):
        return Server(loop=self._loop, handler=self._handler, app=self)

    async def _handler(self, request, response_writer):
        """Process incoming request"""
        try:
            match_info, handler = self._router.resolve(request)
            request.match_info = match_info

            if self._middlewares:
                for md in self._middlewares:
                    handler = partial(md, handler=handler)

            resp = await handler(request)
        except HTTPException as e:
            resp = e
        except Exception as exc:
            resp = format_exception(exc)

        if not isinstance(resp, Response):
            raise RuntimeError(f'expect Response instance but got {type(resp)}')

        response_writer(resp)

    async def startup(self):
        coros = [func(self) for func in self._on_startup]
        await asyncio.gather(*coros, loop=self._loop)

    async def shutdown(self):
        coros = [func(self) for func in self._on_shutdown]
        await asyncio.gather(*coros, loop=self._loop)


def run_app(app, host="127.0.0.1", port=8080, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()

    instance = app._make_server()

    loop.run_until_complete(app.startup())

    server = loop.run_until_complete(
        loop.create_server(lambda: instance, host=host, port=port)
    )

    try:
        loop.add_signal_handler(
            signal.SIGTERM, lambda: asyncio.ensure_future(app.shutdown())
        )
    except NotImplementedError:
        pass  # Ignore if not implemented. Means this program is running in windows.

    try:
        print(f'Started server on {host}:{port}')
        loop.run_until_complete(server.serve_forever())
    except KeyboardInterrupt:
        loop.run_until_complete(app.shutdown())
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.stop()
