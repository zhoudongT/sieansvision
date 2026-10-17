"""Local-only test server with single-bit semantics missing in upstream 3.2.1.

Upstream's server discards the bit offset and treats BIT as a byte. This narrow
subclass handles BIT requests directly; the production client is unmodified.
Private server hooks are pinned and covered by protocol round-trip tests.
"""
import struct
from s7 import Server


class S7TestServer(Server):
    def _bit_response(self,request,writing):
        addr=request.get('parameters',{}).get('address_spec',{})
        if addr.get('word_len')!=1: return None
        params=request.get('raw_parameters',b'')
        if len(params)!=14 or params[1]!=1 or addr.get('count')!=1:
            return self._build_error_response(request,0x8001)
        key=(addr['area'],addr['db_number'])
        memory=self.memory_areas.get(key)
        offset=addr['start']
        if memory is None or offset<0 or offset>=len(memory):
            return self._build_error_response(request,0x8404)
        bit=params[13]&7
        with self.area_locks[key]:
            if writing:
                data=request.get('data',{})
                if data.get('transport_size')!=3 or data.get('data') not in (b'\x00',b'\x01'):
                    return self._build_error_response(request,0x8001)
                mask=1<<bit
                memory[offset]=(memory[offset]|mask) if data['data'][0] else (memory[offset]&~mask)
                payload=b'\xff'
            else:
                payload=struct.pack('>BBHB',0xff,3,1,(memory[offset]>>bit)&1)
        return struct.pack('>BBHHHHBB',0x32,3,0,request['sequence'],2,len(payload),0,0)+bytes([5 if writing else 4,1])+payload

    def _handle_read_area(self,request,client_address):
        response=self._bit_response(request,False)
        return response if response is not None else super()._handle_read_area(request,client_address)

    def _handle_write_area(self,request,client_address):
        response=self._bit_response(request,True)
        return response if response is not None else super()._handle_write_area(request,client_address)
