import collections
import os
import subprocess
import select
import selectors

from time import monotonic as _time


class UnixInteractiveProcess(subprocess.Popen):
    stdin_buffer = None
    stdout_buffer = None
    stderr_buffer = None
    _write_ready = False

    _PIPE_BUF = getattr(select, 'PIPE_BUF', 512)
    if hasattr(selectors, 'PollSelector'):
        _PopenSelector = selectors.PollSelector
    else:
        _PopenSelector = selectors.SelectSelector

    def interact(self, timeout=None):
        """
        Listen to stdout and stderr, calling `handle_output`
        when data is available.

        :param timeout:
        :return: None
        """
        if timeout is not None:
            endtime = _time() + timeout
        else:
            endtime = None

        # use a deque containing chunks to write / as read
        # readers can consume from the queue to reduce memory impact
        if self.stdin:
            self.stdin_buffer = collections.deque()
        if self.stdout:
            self.stdout_buffer = collections.deque()
        if self.stderr:
            self.stderr_buffer = collections.deque()

        with self._PopenSelector() as selector:
            if self.stdin:
                selector.register(self.stdin, selectors.EVENT_WRITE)
            if self.stdout:
                selector.register(self.stdout, selectors.EVENT_READ)
            if self.stderr:
                selector.register(self.stderr, selectors.EVENT_READ)

            while selector.get_map():
                new_timeout = self._remaining_time(endtime)
                if new_timeout is not None and new_timeout < 0:
                    raise subprocess.TimeoutExpired(self.args, timeout)

                ready = selector.select(new_timeout)
                self._check_timeout(endtime, timeout)

                for key, events in ready:
                    if key.fileobj is self.stdin:
                        self._write_ready = True
                    elif key.fileobj in (self.stdout, self.stderr):
                        data = os.read(key.fd, 32768)
                        if not data:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        if key.fileobj is self.stdout:
                            self.stdout_buffer.append(data)
                            self.handle_output(self.stdout_buffer)
                        else:
                            self.stderr_buffer.append(data)
                            self.handle_output(self.stderr_buffer)

                if self._write_ready:
                    if self.stdin_buffer:
                        chunk = self.stdin_buffer.popleft()
                        try:
                            written = os.write(self.stdin.name, chunk)
                            if written < len(chunk):
                                # put the remainder of the chunk back on the queue
                                # for next time. inefficiently small, but unlikely...
                                self.stdin_buffer.appendleft(chunk[written:])
                        except BrokenPipeError:
                            selector.unregister(self.stdin)
                            self.stdin.close()
                        if self.stdin.name not in selector.get_map():
                            # add back a listener now that we have written
                            selector.register(self.stdin, selectors.EVENT_WRITE)
                    elif self.stdin.name in selector.get_map():
                        # nothing to write at the moment, remove from selector
                        selector.unregister(self.stdin)

        self.wait(timeout=self._remaining_time(endtime))

    def write_input(self, data):
        """
        Enqueue data for writing in stdin. Breaks data into chunks
        of the size that will be written, for efficiency.

        :param data: bytes
        :return: None
        """
        if not self.stdin:
            raise RuntimeError('Cannot write to stdin if PIPE was not specified.')
        if self.stdin_buffer is None:
            self.stdin_buffer = collections.deque()

        for i in range(0, len(data), self._PIPE_BUF):
            self.stdin_buffer.append(data[i:i + self._PIPE_BUF])

    def handle_output(self, queue):
        """
        Called when data is received from the subprocess on either
        stdout or stderr.

        Implementations may call `self.stdin.write(bytes)` to send data
        to the subprocess.

        :param queue: either self.stdout_buffer or self.stderr_buffer
        :return: None
        """

