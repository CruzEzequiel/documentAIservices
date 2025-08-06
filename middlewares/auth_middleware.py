"""
Módulo: token_validator

Este módulo provee la dependencia `validate_access_token` para proteger rutas en FastAPI.

### Métodos de autenticación

1. **Access Token estático** (_deprecated_)
   - Variable de entorno: `ACCESS_TOKEN`
   - Solo por compatibilidad temporal.

2. **Firebase ID Token**
   - ID Token JWT emitido por Firebase Authentication.
   - Verificación manual de firma RS256 contra certificados X.509 de Firebase.
   - Reclamos verificados: `exp`, `aud`, `iss`, `sub`.

### Caching de certificados X.509
Los certificados públicos de Firebase se almacenan en memoria (`_certs`) junto con su tiempo de expiración (`_certs_expiry`) según `Cache-Control: max-age`. Se usan con un lock para seguridad ante múltiples hilos; al expirar se redescargan.

### Comportamiento de errores
- Falta o formato incorrecto de la cabecera → `HTTPException 401 Unauthorized`
- Verificación fallida o usuario no admin → `HTTPException 403 Forbidden`
"""

import os
import time
import threading
import requests
import secrets
from fastapi import Header, HTTPException, status
from dotenv import load_dotenv
import jwt
from jwt import ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError, InvalidSignatureError
from cryptography import x509
from cryptography.hazmat.primitives import serialization

# Cargar variables de entorno
load_dotenv('.env')

# TOKEN ESTÁTICO (compatibilidad, deprecated)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
# ID de proyecto Firebase para aud/iss
PROJECT_ID   = os.getenv("FIREBASE_PROJECT_ID")

# Validar configuración mínima
if not PROJECT_ID:
    raise ValueError(
        "El ID de proyecto de Firebase no está configurado. Define 'FIREBASE_PROJECT_ID' en .env."
    )

# URL de certificados públicos de Firebase
_CERT_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)

# Caché de certificados
_certs = None
_certs_expiry = 0
_certs_lock = threading.Lock()

def _get_firebase_certs():
    """
    Descarga y cachea los certificados X.509 de Firebase.
    Retorna dict { kid: cert_pem } protegido por lock.
    Imprime si se usa caché o se realiza petición.
    """
    global _certs, _certs_expiry
    with _certs_lock:
        if _certs and time.time() < _certs_expiry:
            print(f"🔄 Usando certificados cacheados hasta {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_certs_expiry))}")
            return _certs

        print("🌐 Caché expirado o no existente; descargando certificados...")
        resp = requests.get(_CERT_URL)
        resp.raise_for_status()

        cache_control = resp.headers.get("Cache-Control", "")
        max_age = 0
        for part in cache_control.split(','):
            if part.strip().startswith('max-age'):
                _, val = part.split('=', 1)
                try:
                    max_age = int(val)
                except ValueError:
                    pass

        _certs = resp.json()
        _certs_expiry = time.time() + max_age
        print(f"✅ Certificados actualizados; expiran en {max_age}s hasta {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_certs_expiry))}")
        return _certs

def _verify_firebase_jwt(id_token: str) -> dict:
    """
    Verifica manualmente un Firebase ID Token:
      - Obtiene 'kid' del header JWT.
      - Carga certificado del caché.
      - Convierte X.509 a clave pública PEM.
      - Decodifica y valida reclamos con PyJWT.
    Retorna payload o lanza ValueError.
    """
    # Extraer header de manera segura
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.DecodeError:
        raise ValueError('JWT malformado: no contiene segmentos válidos')

    kid = header.get('kid')
    alg = header.get('alg')
    if alg != 'RS256' or not kid:
        raise ValueError('Encabezado JWT inválido')

    certs = _get_firebase_certs()
    cert_pem = certs.get(kid)
    if not cert_pem:
        raise ValueError(f'Clave pública desconocida: {kid}')

    # Parsear certificado X.509 a clave pública PEM
    cert_obj = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'))
    public_key = cert_obj.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    try:
        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=['RS256'],
            audience=PROJECT_ID,
            issuer=f'https://securetoken.google.com/{PROJECT_ID}',
        )
    except ExpiredSignatureError:
        raise ValueError('Token JWT expirado')
    except InvalidAudienceError:
        raise ValueError('Audience inválido en JWT')
    except InvalidIssuerError:
        raise ValueError('Issuer inválido en JWT')
    except InvalidSignatureError:
        raise ValueError('Firma JWT inválida')
    except Exception as e:
        raise ValueError(f'Error verificando JWT: {e}')

    if not payload.get('sub'):
        raise ValueError("Claim 'sub' inválido en JWT")
    return payload

def validate_access_token(authorization: str = Header(None)):
    """
    Dependencia de FastAPI:
    1) Si ACCESS_TOKEN está definido y coincide → OK.
    2) Verificar Firebase ID Token.
    Sino → HTTPException 401/403.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso requerido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de cabecera inválido. Use 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # 1) Verificar token estático (deprecated)
    if ACCESS_TOKEN and secrets.compare_digest(token, ACCESS_TOKEN):
        return

    # 2) Verificar Firebase JWT
    try:
        payload = _verify_firebase_jwt(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this resource",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return
