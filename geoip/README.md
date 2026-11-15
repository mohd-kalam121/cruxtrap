# GeoIP database (optional)

Place MaxMind's free **GeoLite2-City.mmdb** here to enrich public attacker IPs with
country and city. It requires a free MaxMind account and is licensed, so it is not
committed (`*.mmdb` is git-ignored).

1. Create an account at https://www.maxmind.com/en/geolite2/signup
2. Download *GeoLite2 City* (GeoIP2 Binary `.mmdb`)
3. Save it as `geoip/GeoLite2-City.mmdb`
4. `docker compose restart pipeline`

Without it, loopback and private addresses are still labelled; public IPs show as unknown.
Locations are applied when an attacker is first seen.
