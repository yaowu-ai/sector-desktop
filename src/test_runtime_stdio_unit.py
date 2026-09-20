import io

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
