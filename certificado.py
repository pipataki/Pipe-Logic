# Pipe-Logic -- editor de símbolos lógicos y matemáticos, con voz.
# Copyright (C) 2026  pipataki <pipataki@pipataki.net>
#
# Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
# los terminos de la Licencia Publica General Reducida GNU (LGPL) publicada
# por la Free Software Foundation, en su version 3 o cualquier posterior.
# Se distribuye SIN NINGUNA GARANTIA. Ver LICENSE y <https://www.gnu.org/licenses/>.

"""Certificados para servir Pipe-Logic por HTTPS sin aviso del navegador.

Como hace mkcert: una AUTORIDAD local de Pipe-Logic (ca.pem) firma el
certificado del servidor (cert.pem). La autoridad se importa UNA vez en el
navegador (lo hace pipataki; ver ESTADO.md) y desde entonces no hay aviso.
Si se regenera el del servidor, la autoridad sigue valiendo.

La clave de la autoridad (ca-clave.pem) no sale de certificado/ ni de git:
quien la tenga puede firmar certificados que ese navegador creera.

Adaptado de VoiceController (webapp/app.py, _get_or_create_self_signed_cert,
LGPLv3). Si se arregla algo aqui, mirar si toca alli tambien.
"""

import datetime
import ipaddress
from pathlib import Path

import config

CARPETA = Path(__file__).resolve().parent / "certificado"
CA = CARPETA / "ca.pem"
CA_CLAVE = CARPETA / "ca-clave.pem"
CERT = CARPETA / "cert.pem"
CLAVE = CARPETA / "clave.pem"


def _escribir_clave(ruta, clave):
    from cryptography.hazmat.primitives import serialization
    ruta.write_bytes(clave.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    ruta.chmod(0o600)


def _la_autoridad():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    if CA.exists() and CA_CLAVE.exists():
        ca = x509.load_pem_x509_certificate(CA.read_bytes())
        clave = serialization.load_pem_private_key(CA_CLAVE.read_bytes(), None)
        return ca, clave

    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                           "Pipe-Logic (autoridad local)")])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    ca = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora)
        .not_valid_after(ahora + datetime.timedelta(days=3650))
        # pathlen=0: solo puede firmar certificados de servidor, no otras
        # autoridades.
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave.public_key()),
                       critical=False)
        .sign(clave, hashes.SHA256())
    )
    CARPETA.mkdir(exist_ok=True)
    CA.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    _escribir_clave(CA_CLAVE, clave)
    return ca, clave


def _nombres_al_dia():
    """¿Lleva el certificado del servidor todos los nombres de config?
    Si se añade una dirección (config_local), se rehace solo; la autoridad
    no cambia, así que el navegador no vuelve a avisar."""
    from cryptography import x509
    cert = x509.load_pem_x509_certificate(CERT.read_bytes())
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False
    tiene = {str(v) for v in san.get_values_for_type(x509.DNSName)}
    tiene |= {str(v) for v in san.get_values_for_type(x509.IPAddress)}
    return set(config.NOMBRES_CERTIFICADO) <= tiene


def el_certificado():
    """Devuelve (cert, clave) del servidor; los genera si faltan."""
    if CERT.exists() and CLAVE.exists() and CA.exists() and _nombres_al_dia():
        return str(CERT), str(CLAVE)

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    ca, ca_clave = _la_autoridad()
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Un certificado con un solo nombre falla en cuanto se entra por otro
    # ("localhost" frente a "127.0.0.1"): van todos los de config.
    alternativos = []
    for n in config.NOMBRES_CERTIFICADO:
        try:
            alternativos.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            alternativos.append(x509.DNSName(n))

    ahora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Pipe-Logic")]))
        .issuer_name(ca.subject)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora)
        .not_valid_after(ahora + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alternativos), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                       critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_clave.public_key()),
                       critical=False)
        .sign(ca_clave, hashes.SHA256())
    )
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    _escribir_clave(CLAVE, clave)
    return str(CERT), str(CLAVE)
