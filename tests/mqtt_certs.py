"""Generate ephemeral TLS fixtures; no production keys or trust changes."""
import datetime
import ipaddress
import pathlib
import sys
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

directory = pathlib.Path(sys.argv[1])
now = datetime.datetime.now(datetime.timezone.utc)
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SIEANS MQTT test CA')])
ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
      .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
      .not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(days=1))
      .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).sign(ca_key, hashes.SHA256()))
(directory / 'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
for role in ('server', 'client', 'wronghost'):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, role)])
    builder = (x509.CertificateBuilder().subject_name(name).issuer_name(ca_name)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(days=1))
               .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH if role == 'client' else ExtendedKeyUsageOID.SERVER_AUTH]), critical=False))
    if role != 'client':
        builder = builder.add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.2' if role == 'wronghost' else '127.0.0.1'))]), critical=False)
    (directory / (role + '.pem')).write_bytes(builder.sign(ca_key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
    (directory / (role + '-key.pem')).write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
