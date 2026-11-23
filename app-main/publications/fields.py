"""Model fields that work around MariaDB GIS quirks (FA-R101)."""
import functools
import re

from django.contrib.gis.db import models as geo_models
from django.contrib.gis.db.backends.base.adapter import WKTAdapter
from django.contrib.gis.db.models.lookups import GISLookup

_POINT_PARENS_RE = re.compile(r'\(\s*([^()]*?)\s*\)')


def mariadb_multipoint_wkt(wkt):
    """``wkt`` with a MULTIPOINT written as ``MULTIPOINT (x y, ...)``.

    GEOS 3.12+ writes ``MULTIPOINT ((x y), ...)`` (the OGC form). MariaDB 11.2's
    ST_GeomFromText returns NULL for that form, without an error, but reads the older form
    without the parentheses around each point. Other WKT is returned unchanged."""
    if not wkt.startswith('MULTIPOINT') or '(' not in wkt:
        return wkt
    head, body = wkt.split('(', 1)
    return head + '(' + _POINT_PARENS_RE.sub(r'\1', body)


def _fix_adapter(value, connection):
    """Rewrite the WKT of a MySQL/MariaDB geometry parameter (see mariadb_multipoint_wkt)."""
    if isinstance(value, WKTAdapter) and connection.vendor == 'mysql':
        value.wkt = mariadb_multipoint_wkt(value.wkt)
    return value


@functools.cache
def _mariadb_lookup(lookup_class):
    """``lookup_class`` (a GIS lookup) sending its geometry in the WKT MariaDB reads.
    GIS lookups build their parameter themselves, not through the field."""
    def get_db_prep_lookup(self, value, connection):
        sql, params = super(cls, self).get_db_prep_lookup(value, connection)
        return sql, [_fix_adapter(param, connection) for param in params]

    cls = type(lookup_class.__name__, (lookup_class,), {
        'get_db_prep_lookup': get_db_prep_lookup, '__module__': __name__})
    return cls


class MultiPointField(geo_models.MultiPointField):
    """MultiPointField that MariaDB stores instead of NULL (see mariadb_multipoint_wkt), for
    saving and for GIS lookups.

    Deconstructs as Django's MultiPointField, so migrations are unchanged."""

    def get_db_prep_value(self, value, connection, *args, **kwargs):
        return _fix_adapter(super().get_db_prep_value(value, connection, *args, **kwargs),
                            connection)

    def get_lookup(self, lookup_name):
        lookup = super().get_lookup(lookup_name)
        if isinstance(lookup, type) and issubclass(lookup, GISLookup):
            return _mariadb_lookup(lookup)
        return lookup

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return name, 'django.contrib.gis.db.models.fields.MultiPointField', args, kwargs
