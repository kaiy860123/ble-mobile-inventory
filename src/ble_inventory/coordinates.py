"""WGS84 ECEF / local tangent plane conversion, without a network dependency."""
from dataclasses import dataclass
import math

A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)


def geodetic_to_ecef(latitude_deg, longitude_deg, height_m=0.0):
    lat, lon = map(math.radians, (latitude_deg, longitude_deg))
    n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    return ((n + height_m) * math.cos(lat) * math.cos(lon),
            (n + height_m) * math.cos(lat) * math.sin(lon),
            (n * (1 - E2) + height_m) * math.sin(lat))


def ecef_to_geodetic(x, y, z):
    p = math.hypot(x, y)
    lon = math.atan2(y, x)
    if p < 1e-9:
        b = A * (1 - F)
        return math.copysign(90.0, z), 0.0, abs(z) - b
    lat = math.atan2(z, p * (1 - E2))
    for _ in range(12):
        n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
        new_lat = math.atan2(z + E2 * n * math.sin(lat), p)
        if abs(new_lat - lat) < 1e-14:
            lat = new_lat
            break
        lat = new_lat
    n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), h


@dataclass(frozen=True)
class GeoReference:
    latitude_deg: float
    longitude_deg: float
    height_m: float = 0.0
    rotation_deg: float = 0.0
    transform_id: str = "site-v1"
    source: str = "measured"

    def __post_init__(self):
        values = (self.latitude_deg, self.longitude_deg, self.height_m, self.rotation_deg)
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError("Georeference values must be finite")
        if not -90 <= self.latitude_deg <= 90 or not -180 <= self.longitude_deg <= 180:
            raise ValueError("Invalid WGS84 latitude/longitude")

    def _matrix(self):
        lat, lon = map(math.radians, (self.latitude_deg, self.longitude_deg))
        return ((-math.sin(lon), math.cos(lon), 0),
                (-math.sin(lat)*math.cos(lon), -math.sin(lat)*math.sin(lon), math.cos(lat)),
                (math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)))

    def to_wgs84(self, x_m, y_m, z_m=0.0):
        t = math.radians(self.rotation_deg)
        enu = (math.cos(t)*x_m-math.sin(t)*y_m, math.sin(t)*x_m+math.cos(t)*y_m, z_m)
        origin = geodetic_to_ecef(self.latitude_deg, self.longitude_deg, self.height_m)
        matrix = self._matrix()
        xyz = [origin[j]+sum(matrix[i][j]*enu[i] for i in range(3)) for j in range(3)]
        lat, lon, h = ecef_to_geodetic(*xyz)
        return {"latitude_deg": lat, "longitude_deg": lon, "height_m": h, "transform_id": self.transform_id}

    def to_local(self, latitude_deg, longitude_deg, height_m=None):
        h = self.height_m if height_m is None else height_m
        xyz = geodetic_to_ecef(latitude_deg, longitude_deg, h)
        origin = geodetic_to_ecef(self.latitude_deg, self.longitude_deg, self.height_m)
        delta = [xyz[i]-origin[i] for i in range(3)]
        e, n, u = [sum(row[i]*delta[i] for i in range(3)) for row in self._matrix()]
        t = math.radians(self.rotation_deg)
        return {"x_m": math.cos(t)*e+math.sin(t)*n, "y_m": -math.sin(t)*e+math.cos(t)*n, "z_m": u}
