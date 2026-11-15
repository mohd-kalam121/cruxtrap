"""GeoIP enrichment. Uses a MaxMind GeoLite2-City database if one is present; otherwise
classifies private/loopback ranges and leaves public IPs unresolved (dashboard shows '—').

GeoLite2 is free but needs a MaxMind account to download, so it is not committed. Put
the .mmdb at data/GeoLite2-City.mmdb (or set GEOIP_DB) and restart the pipeline.
"""
from __future__ import annotations

import ipaddress
import logging

log = logging.getLogger("pipeline.geoip")

EMPTY = {"country_code": None, "country": None, "city": None, "latitude": None, "longitude": None, "asn": None, "org": None}


class GeoIP:
    def __init__(self, path: str | None):
        self.reader = None
        if path:
            try:
                import geoip2.database
                self.reader = geoip2.database.Reader(path)
                log.info("GeoIP database loaded: %s", path)
            except (ImportError, OSError, ValueError) as e:
                log.warning("GeoIP disabled (%s)", e)
        self.cache: dict[str, dict] = {}

    def lookup(self, ip: str) -> dict:
        if ip in self.cache:
            return self.cache[ip]
        result = dict(EMPTY)
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return result
        if addr.is_loopback:
            result.update(country_code="LO", country="Loopback", city="localhost")
        elif addr.is_private or addr.is_link_local:
            result.update(country_code="PR", country="Private network")
        elif self.reader is not None:
            try:
                r = self.reader.city(ip)
                result.update(country_code=r.country.iso_code, country=r.country.name, city=r.city.name,
                              latitude=r.location.latitude, longitude=r.location.longitude)
            except Exception as e:  # noqa: BLE001 - AddressNotFoundError and friends
                log.debug("no GeoIP record for %s: %s", ip, e)
        self.cache[ip] = result
        return result

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()
