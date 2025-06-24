import ssl
from requests.adapters import HTTPAdapter


# Creating custom context which enforces TLS v1 and weak cipher bypass
class TLSv1Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.set_ciphers("DEFAULT@SECLEVEL=0")
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)
