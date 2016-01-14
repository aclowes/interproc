import asyncio
import logging
import subprocess
import sys
import unittest

from interproc import UnixInteractiveProcess, run_subprocess_shell

logging.basicConfig(level=logging.DEBUG)

if sys.platform == 'win32':
    loop = asyncio.ProactorEventLoop()  # for subprocess pipes on Windows
    asyncio.set_event_loop(loop)
else:
    loop = asyncio.get_event_loop()

CMD = 'echo starting && cat && echo stopping 1>&2'


class AsyncioTests(unittest.TestCase):
    """
    Document the base Asyncio behavior
    """
    def test_asyncio_create_subprocess(self):
        @asyncio.coroutine
        def run_process():
            future = asyncio.create_subprocess_shell(
                    CMD, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc = yield from future
            stdout, stderr = yield from proc.communicate(b'something\n')
            return stdout, stderr, proc

        stdout, stderr, proc = loop.run_until_complete(run_process())
        self.assertEqual(stdout, b'starting\nsomething\n')
        self.assertEqual(stderr, b'stopping\n')
        self.assertEqual(proc.returncode, 0)


class InteractiveAsyncioTests(unittest.TestCase):
    """
    Test the callback functionality provided by `run_subprocess_shell`
    """
    def test_interactive_asyncio(self):
        def callback(process, fd, data):
            if data == b'starting\n':
                process.stdin.write(b'something\n')
            if data == b'something\n':
                process.stdin.close()

        # option 1: run entirely in an event loop
        # take a coroutine that gets called when data is received
        process = run_subprocess_shell(CMD, callback)
        # exits loop when both pipes have been closed
        self.assertEqual(process.returncode, 0)


class PollingTests(unittest.TestCase):
    """
    Test the `UnixInteractiveProcess.interact()` functionality
    """
    def test_polling_interaction(self):
        class TestProcess(UnixInteractiveProcess):
            def handle_output(self, queue):
                if queue is self.stdout_buffer:
                    data = queue.popleft()
                    if data == b'starting\n':
                        self.write_input(b'something\n')
                    if data == b'something\n':
                        self.stdin.close()  # tell cat to stop waiting for input

        process = TestProcess(
                [CMD], shell=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        process.interact()
        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stderr_buffer.popleft(), b'stopping\n')

if __name__ == '__main__':
    unittest.main()
