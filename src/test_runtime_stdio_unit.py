import io
import unittest
from unittest.mock import patch

import runtime_cli


class BrokenFlushStream(io.StringIO):
    def flush(self):
        raise OSError(22, "Invalid argument")


def test_runtime_stdio_wrapper_absorbs_invalid_flush():
    stream = BrokenFlushStream()
    safe_stream = runtime_cli.SafeTextStream(stream)

    safe_stream.write("runtime output")
    safe_stream.flush()

    assert stream.getvalue() == "runtime output"


class RuntimeEncodingTests(unittest.TestCase):
    def test_install_safe_stdio_uses_utf8_for_both_pipes(self):
        stdout_bytes, stderr_bytes = io.BytesIO(), io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding='gbk', newline='\n')
        stderr = io.TextIOWrapper(stderr_bytes, encoding='gbk', newline='\n')
        with patch.object(runtime_cli.sys, 'stdout', stdout), patch.object(runtime_cli.sys, 'stderr', stderr):
            runtime_cli.install_safe_stdio()
            runtime_cli.sys.stdout.write('视频已接收😀\n')
            runtime_cli.sys.stderr.write('上传检查错误\n')
            runtime_cli.sys.stdout.flush()
            runtime_cli.sys.stderr.flush()
            self.assertEqual(stdout_bytes.getvalue().decode('utf-8'), '视频已接收😀\n')
            self.assertEqual(stderr_bytes.getvalue().decode('utf-8'), '上传检查错误\n')
