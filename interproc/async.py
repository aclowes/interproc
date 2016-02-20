from asyncio import events
from asyncio import streams
from asyncio.coroutines import coroutine
from asyncio.subprocess import SubprocessStreamProtocol, Process
from subprocess import PIPE


class InteractiveSubprocessProtocol(SubprocessStreamProtocol):
    """
    A protocol that makes a callback when stdout or stderr are received
    """
    _callback = None
    _process = None

    def pipe_data_received(self, fd, data):
        super().pipe_data_received(fd, data)
        if self._callback:
            self._callback(self._process, fd, data)

    def configure_handler(self, process, callback):
        self._process = process
        self._callback = callback
        # we may already have received some data; check...
        if self.stdout._buffer:
            self._callback(self._process, 1, self.stdout._buffer)
        if self.stderr._buffer:
            self._callback(self._process, 2, self.stderr._buffer)

# argh http://stackoverflow.com/questions/24435987
# this will print the output, but still you have no way to interact with the process


def run_subprocess_shell(cmd, callback, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                         loop=None, limit=streams._DEFAULT_LIMIT, **kwds):
    if loop is None:
        loop = events.get_event_loop()

    def protocol_factory():
        return InteractiveSubprocessProtocol(limit=limit, loop=loop)

    @coroutine
    def run_subprocess():
        transport, protocol = yield from loop.subprocess_shell(
                protocol_factory,
                cmd, stdin=stdin, stdout=stdout,
                stderr=stderr, **kwds)
        process = Process(transport, protocol, loop)
        protocol.configure_handler(process, callback)
        yield from process.wait()
        return process

    output = loop.run_until_complete(run_subprocess())
    return output
