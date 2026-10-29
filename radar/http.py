import logging
import random
import time

import requests

log = logging.getLogger("radar")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"})


def get(url, *, params=None, data=None, tries=3, timeout=25, **kw):
    """GET/POST com retry e pausa educada entre tentativas. Devolve Response ou None."""
    for attempt in range(1, tries + 1):
        try:
            if data is not None:
                r = session.post(url, params=params, data=data, timeout=timeout, **kw)
            else:
                r = session.get(url, params=params, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            log.warning("HTTP %s em %s (tentativa %d)", r.status_code, url, attempt)
            if r.status_code in (401, 403, 404):
                return None
        except requests.RequestException as e:
            log.warning("Erro em %s: %s (tentativa %d)", url, e, attempt)
        time.sleep(2 * attempt + random.random())
    return None
