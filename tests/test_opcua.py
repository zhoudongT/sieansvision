import asyncio
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'industrial'))
from asyncua import Server, ua
from asyncua.server.user_managers import User, UserRole
from opcua_adapter import run_async, typed_value, validate
from opcua_simulator import create_server

logging.getLogger('asyncua').setLevel(logging.CRITICAL)

class ConfigTests(unittest.TestCase):
    def test_integer_and_scalar_validation(self):
        self.assertEqual(typed_value('18446744073709551615','UInt64'),2**64-1)
        self.assertEqual(typed_value('-9223372036854775808','Int64'),-2**63)
        self.assertAlmostEqual(typed_value(12.1,'Float'),12.100000381469727)
        for value,kind in [(True,'UInt16'),(-1,'UInt16'),(65536,'UInt16'),(2**63,'UInt64'),('x','Int64'),(float('nan'),'Double'),(1e40,'Float'),(1,'Boolean'),([[1]],'Int16'),('2026-01-01','DateTime')]:
            with self.subTest(kind=kind,value=value),self.assertRaises((ValueError,OverflowError)):typed_value(value,kind)

    def test_endpoint_and_auth_rejected_before_network(self):
        for params in [{'endpoint':'http://localhost:4840/'},{'endpoint':'opc.tcp://user:secret@localhost:4840/'},{'endpoint':'opc.tcp://localhost:4840/','username':'user'},{'endpoint':'opc.tcp://localhost:4840/','password':'secret'},{'endpoint':'opc.tcp://localhost:4840/','nodeId':'invalid'}]:
            with self.subTest(params=params),self.assertRaises(ValueError):validate('opcua_read',params)

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server,self.ns,self.nodes=await create_server()
        await self.server.start()
        self.endpoint=f'opc.tcp://127.0.0.1:{self.server.bserver.port}/sieans/'

    async def asyncTearDown(self):await self.server.stop()

    async def call(self,action,node='Count',**params):
        return (await run_async('opcua_'+action,{'endpoint':self.endpoint,'nodeId':f'ns={self.ns};s=SIEANS.{node}','timeoutMs':3000,**params}))['result']

    async def test_typed_write_read_arrays_and_exact_int64(self):
        await self.call('write',value=23,dataType='UInt32')
        out=await self.call('read');self.assertEqual(out['value'],23);self.assertEqual(out['dataType'],'UInt32');self.assertEqual(out['quality'],'good');self.assertTrue(out['serverTimestamp'])
        await self.call('write','Samples',value=[12.5,-3.25],dataType='Double')
        out=await self.call('read','Samples');self.assertEqual(out['value'],[12.5,-3.25]);self.assertTrue(out['isArray'])
        node=await self.server.nodes.objects.add_variable(ua.NodeId('Big',self.ns),'Big',ua.Variant(2**64-1,ua.VariantType.UInt64))
        out=await self.call('read',nodeId=node.nodeid.to_string());self.assertEqual(out['value'],'18446744073709551615')

    async def test_namespace_uri_resolves_changed_namespace_index(self):
        out=await self.call('read',nodeId='ns=99;s=SIEANS.Height',namespaceUri='urn:sieans:simulator');self.assertEqual(out['value'],12.5);self.assertEqual(out['nodeId'],f'ns={self.ns};s=SIEANS.Height')

    async def test_browse_root_and_truncated_children(self):
        out=await self.call('browse',nodeId='i=85');self.assertTrue(any(i['browseName']=='SIEANS' for i in out['items']))
        out=await self.call('browse',nodeId=f'ns={self.ns};s=SIEANS',browseLimit=2);self.assertEqual(out['count'],2);self.assertTrue(out['truncated']);self.assertEqual(out['items'][0]['namespaceUri'],'urn:sieans:simulator')
        out=await self.call('browse',nodeId=f'ns={self.ns};s=SIEANS');self.assertEqual(out['count'],6);self.assertFalse(out['truncated'])

    async def test_quality_unknown_node_readonly_and_type_mismatch(self):
        with self.assertRaisesRegex(ValueError,'BadNodeIdUnknown'):await self.call('read','Missing')
        with self.assertRaisesRegex(ValueError,'BadUserAccessDenied|BadNotWritable'):await self.call('write','Serial',dataType='String',value='changed')
        self.assertEqual((await self.call('read','Serial'))['value'],'SIM-OPCUA-001')
        with self.assertRaisesRegex(ValueError,'BadTypeMismatch'):await self.call('write','Count',dataType='String',value='3')
        await self.nodes['Height'].write_value(ua.DataValue(ua.Variant(0.0,ua.VariantType.Double),StatusCode=ua.StatusCode(ua.StatusCodes.BadSensorFailure)))
        with self.assertRaisesRegex(ValueError,'数据质量不合格'):await self.call('read','Height')
        out=await self.call('read','Height',requireGood=False);self.assertEqual(out['quality'],'bad');self.assertEqual(out['status'],'BadSensorFailure')

    async def test_float_guid_datetime_and_empty_array(self):
        values=[('Float',1.25),('Guid','12345678-1234-1234-1234-123456789abc'),('DateTime','2026-10-15T12:00:00+00:00'),('ByteString','YWJj')]
        for kind,value in values:
            node=await self.server.nodes.objects.add_variable(ua.NodeId(kind,self.ns),kind,ua.Variant(typed_value(value,kind),getattr(ua.VariantType,kind)));await node.set_writable()
            await self.call('write',nodeId=node.nodeid.to_string(),dataType=kind,value=value)
            self.assertEqual((await self.call('read',nodeId=node.nodeid.to_string()))['value'],value)
        await self.call('write','Samples',dataType='Double',value=[]);self.assertEqual((await self.call('read','Samples'))['value'],[])

    async def test_timeout_is_bounded(self):
        writers=[]
        async def consume(reader,writer):
            writers.append(writer)
            try:await reader.read()
            finally:writer.close()
        async with await asyncio.start_server(consume,'127.0.0.1',0) as blackhole:
            endpoint=f'opc.tcp://127.0.0.1:{blackhole.sockets[0].getsockname()[1]}/'
            start=time.monotonic()
            with self.assertRaisesRegex(ValueError,'超时'):await self.call('read',endpoint=endpoint,timeoutMs=200)
            self.assertLess(time.monotonic()-start,1.5)
            for writer in writers:writer.close()

def certificate(folder,name,uri,server=False,expired=False):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(days=2)).not_valid_after(now+timedelta(days=-1 if expired else 2))
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(uri),x509.DNSName('localhost')]),critical=False)
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=True,key_encipherment=True,data_encipherment=True,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=False,decipher_only=False),critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]),critical=False).sign(key,hashes.SHA256()))
    certpath=Path(folder)/(name+'.der');keypath=Path(folder)/(name+'.pem')
    certpath.write_bytes(cert.public_bytes(serialization.Encoding.DER));keypath.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    return str(certpath),str(keypath)

class SecureTests(unittest.IsolatedAsyncioTestCase):
    async def test_encrypted_username_auth_certificate_pin_and_bad_password(self):
        class Users:
            def get_user(self,iserver,username=None,password=None,certificate=None):
                return User(role=UserRole.User) if username=='operator' and password=='test-only-password' else None
        with tempfile.TemporaryDirectory() as folder:
            server_cert,server_key=certificate(folder,'server','urn:sieans:test:server',server=True)
            client_cert,client_key=certificate(folder,'client','urn:sieans:vision:client')
            wrong_cert,_=certificate(folder,'wrong','urn:sieans:test:server',server=True)
            server=Server(user_manager=Users());await server.init();server.set_endpoint('opc.tcp://127.0.0.1:0/secure/')
            await server.set_application_uri('urn:sieans:test:server');await server.load_certificate(server_cert);await server.load_private_key(server_key)
            server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt]);server.set_identity_tokens([ua.UserNameIdentityToken])
            ns=await server.register_namespace('urn:test');node=await server.nodes.objects.add_variable(ua.NodeId('Value',ns),'Value',3);await node.set_writable()
            async with server:
                params={'endpoint':f'opc.tcp://127.0.0.1:{server.bserver.port}/secure/','nodeId':node.nodeid.to_string(),'security':'Basic256Sha256','clientCertificate':client_cert,'privateKey':client_key,'serverCertificate':server_cert,'username':'operator','passwordEnv':'SIEANS_OPCUA_TEST_PASSWORD','timeoutMs':4000}
                old=os.environ.get('SIEANS_OPCUA_TEST_PASSWORD');os.environ['SIEANS_OPCUA_TEST_PASSWORD']='test-only-password'
                try:
                    out=await run_async('opcua_read',params);self.assertEqual(out['result']['value'],'3')
                    await run_async('opcua_write',{**params,'dataType':'Int64','value':'7'})
                    self.assertEqual((await run_async('opcua_read',params))['result']['value'],'7')
                    subscribed=await run_async('opcua_wait',{**params,'comparison':'eq','expectedValue':7,'publishingIntervalMs':20,'waitTimeoutMs':3000})
                    self.assertTrue(subscribed['result']['triggered'])
                    with self.assertRaises(ValueError):await run_async('opcua_read',{**params,'serverCertificate':wrong_cert})
                    os.environ['SIEANS_OPCUA_TEST_PASSWORD']='bad-test-secret'
                    with self.assertRaises(ValueError) as error:await run_async('opcua_read',params)
                    self.assertNotIn('bad-test-secret',str(error.exception))
                    with self.assertRaises(ValueError) as wait_error:await run_async('opcua_wait',{**params,'waitTimeoutMs':3000})
                    self.assertNotIn('bad-test-secret',str(wait_error.exception))
                finally:
                    if old is None:os.environ.pop('SIEANS_OPCUA_TEST_PASSWORD',None)
                    else:os.environ['SIEANS_OPCUA_TEST_PASSWORD']=old

if __name__=='__main__':unittest.main(verbosity=2)
