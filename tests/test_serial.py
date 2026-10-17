import base64
import os
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'industrial'))
from serial_adapter import complete_frame, run


def params(wire=b'ABC\r\n', **values):
    return dict(mode='exchange', simulated=True, timeoutMs=1000, rxFraming='crlf',
                maxBytes=65536, wireBase64=base64.b64encode(wire).decode(), **values)


class FakePort:
    def __init__(self, chunks=(), stale=b'', write_limit=None, stalled=False, error=False):
        self.chunks = list(chunks)
        self.stale = stale
        self.written = b''
        self.write_limit = write_limit
        self.stalled = stalled
        self.error = error
        self.is_open = False
        self.closed = False
        self.reset = False

    def open(self): self.is_open = True
    def close(self): self.closed = True; self.is_open = False
    def reset_input_buffer(self): self.stale = b''; self.reset = True

    @property
    def in_waiting(self): return len(self.stale) or (len(self.chunks[0]) if self.chunks else 0)

    @property
    def out_waiting(self): return 1 if self.stalled else 0

    def write(self, data):
        count = min(len(data), self.write_limit) if self.write_limit is not None else len(data)
        self.written += data[:count]
        return count

    def read(self, length):
        if self.error: raise IOError('device unplugged')
        if self.stale:
            data, self.stale = self.stale[:length], self.stale[length:]
            return data
        if self.chunks:
            data = self.chunks.pop(0)
            if len(data) > length: self.chunks.insert(0, data[length:])
            return data[:length]
        time.sleep(min(self.timeout, .01))
        return b''


class SerialTests(unittest.TestCase):
    def test_real_pyserial_loopback(self):
        for wire, framing, expected in [(b'ABC\r\n','crlf',b'ABC'),(b'\0','nul',b''),
                                       (b'\x00\x03\x00\x80\xff','length16be',b'\x00\x80\xff')]:
            p=params(wire);p['rxFraming']=framing
            result=run(p)['result']
            self.assertEqual(base64.b64decode(result['payloadBase64']),expected)
            self.assertTrue(result['simulated'])
            self.assertFalse(result['acknowledged'])

    def test_fragmented_headers_delimiters_and_coalesced_frames(self):
        payload='中文'.encode()
        for framing,wire in [('crlf',payload+b'\r\n'),('length16be',len(payload).to_bytes(2,'big')+payload),('length32le',len(payload).to_bytes(4,'little')+payload)]:
            fake=FakePort([wire[:1],wire[1:3],wire[3:]+wire])
            p=params();p['rxFraming']=framing
            out=run(p,lambda *a,**kw:fake)['result']
            self.assertEqual(base64.b64decode(out['payloadBase64']),payload)
            self.assertEqual(out['trailingBytes'],len(wire))
            self.assertTrue(fake.closed)

    def test_fixed_frame_limits_and_malformed_headers(self):
        self.assertIsNone(complete_frame(bytearray(b'AB'),'fixed',3,3))
        self.assertEqual(complete_frame(bytearray(b'ABCDE'),'fixed',3,3),(b'ABC',2))
        for data,rule,limit in [(b'ABCD','lf',3),(b'\xff\xff','length16be',100),(b'ABCD\r\n','crlf',3)]:
            with self.assertRaisesRegex(ValueError,'上限'): complete_frame(bytearray(data),rule,limit)
        with self.assertRaises(ValueError): complete_frame(bytearray(),'eof',100)

    def test_receive_only_keeps_stale_input_and_sends_nothing(self):
        fake=FakePort(stale=b'PREVIOUS\r\n');p=params();p.update(mode='receive',simulated=False,serialPort='test-port',clearInput=True)
        result=run(p,lambda *a,**kw:fake)['result']
        self.assertEqual(base64.b64decode(result['payloadBase64']),b'PREVIOUS')
        self.assertEqual(fake.written,b'');self.assertFalse(fake.reset);self.assertTrue(fake.closed)

    def test_clear_input_partial_write_and_port_settings(self):
        fake=FakePort([b'OK\r\n'],stale=b'OLD\r\n',write_limit=2);seen={}
        def factory(name,**options): seen.update(options,port=name);return fake
        p=params();p.update(simulated=False,serialPort='test-port',baudrate=19200,dataBits=7,parity='E',stopbits=2,flowControl='rtscts',rts=False,dtr=False,clearInput=True)
        result=run(p,factory)['result']
        self.assertEqual(fake.written,b'ABC\r\n');self.assertTrue(fake.reset)
        self.assertEqual(result['discardedInputBytes'],5);self.assertEqual(seen['bytesize'],7)
        self.assertEqual(seen['parity'],'E');self.assertEqual(seen['stopbits'],2);self.assertTrue(seen['rtscts'])
        self.assertFalse(fake.rts);self.assertFalse(fake.dtr);self.assertTrue(fake.closed)

    def test_timeouts_no_progress_and_disconnect_always_close(self):
        for fake,pattern in [(FakePort(), '超时'),(FakePort(stalled=True),'超时'),(FakePort(write_limit=0),'进展'),(FakePort(error=True),'unplugged')]:
            p=params();p.update(simulated=False,serialPort='test-port',timeoutMs=100)
            began=time.monotonic()
            with self.assertRaisesRegex(RuntimeError,pattern):run(p,lambda *a,**kw:fake)
            self.assertTrue(fake.closed);self.assertLess(time.monotonic()-began,1)
        fake=FakePort();p=params();p['mode']='send'
        result=run(p,lambda *a,**kw:fake)['result'];self.assertEqual(result['delivery'],'sent');self.assertFalse(result['acknowledged']);self.assertTrue(fake.closed)

    @unittest.skipUnless(os.name=='posix','POSIX PTY check requires Linux/macOS')
    def test_posix_pseudo_terminal(self):
        import threading
        master,slave=os.openpty();name=os.ttyname(slave)
        def device():
            data=os.read(master,100)
            if data: os.write(master,b'PTY-OK\r\n')
        thread=threading.Thread(target=device,daemon=True)
        try:
            thread.start();p=params();p.update(simulated=False,serialPort=name)
            self.assertEqual(base64.b64decode(run(p)['result']['payloadBase64']),b'PTY-OK')
        finally:
            os.close(master);os.close(slave);thread.join(1)


if __name__=='__main__': unittest.main()
