"""Scoped workaround for malformed error strings from Windows Hikrobot CTIs.

Some MVS producers return non-UTF-8 bytes in GCGetLastError's description.
GenICam then raises UnicodeDecodeError instead of the actual GenTL exception.
Only reconstruct precisely identified statuses at the affected query sites;
Harvester retains responsibility for optional features and acquisition deadlines.
No SDK files are edited and no acquisition operation is retried here.
"""
import os
from contextlib import contextmanager, ExitStack
from functools import wraps
from pathlib import Path
from threading import RLock

_lock = RLock()
_NOT_IMPLEMENTED = b'GenTL exception: Requested operation not implemented. (Message from the source: '
_TIMEOUT = b'GenTL exception: Operation timed out. (Message from the source: '
_TIMEOUT_BEFORE_COMPLETION = b'GenTL exception: Operation timed out before completion. (Message from the source: '
_RESOURCE_EXHAUSTED = b'GenTL exception: The requested resource is exhausted. (Message from the source: '
_INVALID_HANDLE = b'GenTL exception: Given handle does not support the operation. (Message from the source: '


def normalize_error(function, prefix, code, exception_type):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except UnicodeDecodeError as error:
            raw = error.object
            suffix = (') (ID: %d)' % code).encode('ascii')
            if (error.encoding.lower().replace('_', '-') == 'utf-8'
                    and raw.startswith(prefix) and raw.endswith(suffix)
                    and len(prefix) <= error.start < error.end <= len(raw) - len(suffix)):
                raise exception_type('Hikrobot GenTL status %d (invalid UTF-8 error description)' % code) from error
            raise
    return call


@contextmanager
def hikrobot_transport(path):
    if (os.name != 'nt' or not path
            or Path(path).name.lower() not in ('mvproduceru3v.cti', 'mvproducergev.cti')):
        yield
        return
    from genicam import gentl
    # Workers own one physical camera operation. Scope also protects nested use;
    # all attributes and DLL search handles are restored on close or failure.
    with _lock, ExitStack() as cleanup:
        cookie = os.add_dll_directory(str(Path(path).parent))
        cleanup.callback(cookie.close)

        def replace(owner, name, value):
            original = getattr(owner, name)
            setattr(owner, name, value)
            cleanup.callback(setattr, owner, name, original)

        prop = gentl.Port.url_info_list
        replace(gentl.Port, 'url_info_list', property(
            normalize_error(normalize_error(normalize_error(prop.fget, _NOT_IMPLEMENTED, -1003, gentl.NotImplementedException),
                            _RESOURCE_EXHAUSTED, -1020, gentl.ResourceExhaustedException),
                            _INVALID_HANDLE, -1006, gentl.InvalidHandleException),
            prop.fset, prop.fdel, prop.__doc__))
        for owner in (gentl.System, gentl.Interface, gentl.Device):
            replace(owner, 'register_event', normalize_error(
                owner.register_event, _NOT_IMPLEMENTED, -1003, gentl.NotImplementedException))
        replace(gentl.EventManagerNewBuffer, 'update_event_data', normalize_error(
            normalize_error(gentl.EventManagerNewBuffer.update_event_data, _TIMEOUT, -1011, gentl.TimeoutException),
            _TIMEOUT_BEFORE_COMPLETION, -1011, gentl.TimeoutException))
        yield
