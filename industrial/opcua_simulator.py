"""Local-only test device. Parent stdin EOF stops the server."""
import asyncio
import json
import sys
from asyncua import Server, ua

async def create_server(endpoint='opc.tcp://127.0.0.1:0/sieans/'):
    server=Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name('SIEANS OPC UA 本机模拟设备')
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    namespace=await server.register_namespace('urn:sieans:simulator')
    root=await server.nodes.objects.add_object(ua.NodeId('SIEANS',namespace),'SIEANS')
    definitions=[('Count',0,ua.VariantType.UInt32,True),('Passed',False,ua.VariantType.Boolean,True),
        ('Height',12.5,ua.VariantType.Double,True),('Label','SIEANS',ua.VariantType.String,True),
        ('Samples',[1.0,2.0,3.0],ua.VariantType.Double,True),('Serial','SIM-OPCUA-001',ua.VariantType.String,False)]
    nodes={}
    for name,value,kind,writable in definitions:
        node=await root.add_variable(ua.NodeId('SIEANS.'+name,namespace),name,ua.Variant(value,kind))
        if writable:await node.set_writable()
        nodes[name]=node
    return server,namespace,nodes

async def main():
    server,namespace,nodes=await create_server()
    async with server:
        port=server.bserver.port
        endpoint=f'opc.tcp://127.0.0.1:{port}/sieans/'
        # Dynamic bind port is assigned after the endpoint descriptions were built.
        server.set_endpoint(endpoint)
        for item in server.iserver.endpoints:item.EndpointUrl=endpoint
        print(json.dumps({'ready':True,'host':'127.0.0.1','port':port,'endpoint':endpoint,'namespaceUri':'urn:sieans:simulator',
            'rootNodeId':f'ns={namespace};s=SIEANS','nodes':{name:node.nodeid.to_string() for name,node in nodes.items()}}),flush=True)
        await asyncio.to_thread(sys.stdin.buffer.read)

if __name__=='__main__':asyncio.run(main())
