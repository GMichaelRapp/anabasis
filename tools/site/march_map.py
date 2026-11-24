"""Draw the march of the Ten Thousand as an atlas plate for the product page.

    python tools/site/march_map.py         # rewrites the <svg class="plate"> in web/index.html

Coastlines and rivers come from the Natural Earth data the app already ships (data/). The route
follows the common modern reconstruction; several sites, Mount Theches among them, are debated.
Colours are CSS variables, so the plate follows the page's light and dark themes.
Needs shapely (pip install shapely) to clip and simplify the coastline; run it only when the plate changes.
"""
import json, math, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W, LON0, LON1, LAT0, LAT1 = 1000, 24.4, 52.6, 28.7, 43.6
K = math.cos(math.radians(36.5))
S = W / ((LON1 - LON0) * K)
H = round((LAT1 - LAT0) * S)


def xy(lon, lat): return ((lon - LON0) * K * S, (LAT1 - lat) * S)


def decode(topo):
    arcs = []
    if 'transform' in topo:  # quantized: delta-encoded integers
        sx, sy = topo['transform']['scale']; tx, ty = topo['transform']['translate']
        for arc in topo['arcs']:
            x = y = 0; pts = []
            for dx, dy in arc:
                x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
            arcs.append(pts)
    else:
        arcs = [[(p[0], p[1]) for p in arc] for arc in topo['arcs']]
    def ring(ix):
        out = []
        for i in ix:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(a if not out else a[1:])
        return out
    def geom(g):
        t, a = g['type'], g.get('arcs')
        if t == 'Polygon': return [ring(r) for r in a]
        if t == 'MultiPolygon': return [ring(r) for p in a for r in p]
        if t == 'LineString': return [ring(a)]
        if t == 'MultiLineString': return [ring(r) for r in a]
        return []
    return geom


def path(lines, closed, tol=0.55):
    """Project, clip to the plate (with a margin) and simplify to sub-pixel detail. Needs shapely."""
    from shapely.geometry import LineString, Polygon, box
    from shapely.ops import unary_union
    frame = box(-40, -40, W + 40, H + 40)
    geoms = []
    for pts in lines:
        if len(pts) < (4 if closed else 2): continue
        if not any(LON0 - 8 < lo < LON1 + 8 and LAT0 - 8 < la < LAT1 + 8 for lo, la in pts): continue
        q = [xy(*p) for p in pts]
        g = Polygon(q).buffer(0) if closed else LineString(q)
        g = g.intersection(frame)
        if not g.is_empty: geoms.append(g)
    if not geoms: return ''
    g = unary_union(geoms) if closed else unary_union(geoms)
    g = g.simplify(tol, preserve_topology=True)
    d = []
    def emit(coords, z):
        c = [(round(x, 1), round(y, 1)) for x, y in coords]
        if len(c) >= 2: d.append('M' + 'L'.join(f'{x:g} {y:g}' for x, y in c) + ('Z' if z else ''))
    def walk(g):
        t = g.geom_type
        if t == 'Polygon':
            emit(g.exterior.coords, True); [emit(r.coords, True) for r in g.interiors]
        elif t == 'LineString': emit(g.coords, False)
        elif hasattr(g, 'geoms'): [walk(x) for x in g.geoms]
    walk(g)
    return ''.join(d)


# The route, west to east and back north (lon, lat)
ROUTE = [(28.04, 38.49), (29.1, 38.3), (30.17, 38.08), (31.2, 38.4), (32.5, 37.87), (34.0, 37.6), (34.75, 37.25),
         (34.9, 36.92), (36.2, 36.85), (36.17, 36.58), (37.3, 36.3), (38.3, 35.95), (39.6, 35.2), (40.9, 34.4),
         (42.3, 33.9), (44.0, 33.3), (44.4, 33.7), (44.0, 34.6), (43.5, 35.6), (43.33, 36.1), (43.15, 36.4),
         (42.9, 36.9), (42.4, 37.35), (41.95, 37.95), (41.8, 38.6), (41.5, 39.15), (41.0, 39.7), (40.2, 40.25),
         (39.85, 40.62), (39.72, 41.0)]
STOPS = [  # (name, lon, lat, label dx, dy, anchor)
    ('Sardis', 28.04, 38.49, 0, -14, 'middle'), ('Tarsus', 34.9, 36.92, -4, 22, 'end'), ('Issus', 36.2, 36.85, 8, -8, 'start'),
    ('Thapsacus', 38.3, 35.95, 10, 18, 'start'), ('Cunaxa', 44.0, 33.3, 8, 20, 'start'), ('Babylon', 44.42, 32.54, 10, 6, 'start'),
    ('Trapezus', 39.72, 41.0, -10, -8, 'end'), ('Mount Theches', 39.85, 40.62, -8, 20, 'end')]
WAY = [  # (numeral, lon, lat, colour, marker offset dx, dy in px)
    ('I', 28.04, 38.49, 'k-sources', 0, 40), ('II', 38.3, 35.95, 'k-notes', -4, -40), ('III', 44.0, 33.3, 'k-docs', -42, 4),
    ('IV', 42.4, 37.35, 'k-outline', -42, 6), ('V', 39.85, 40.62, 'accent', 40, 12)]
REGIONS = [('Lydia', 28.9, 39.35), ('Phrygia', 31.4, 39.25), ('Cilicia', 33.2, 37.05), ('Syria', 37.8, 34.2),
           ('Arabia', 40.6, 32.2), ('Babylonia', 45.6, 31.4), ('Media', 48.2, 35.8), ('Carduchia', 44.6, 37.6),
           ('Armenia', 43.6, 39.6), ('Pontus', 34.9, 40.75), ('Cappadocia', 35.6, 38.85)]
SEAS = [('Pontus Euxinus', 35.0, 42.6, 0), ('Mare Aegaeum', 24.78, 37.75, -90), ('Mare Internum', 30.6, 33.9, 0),
        ('Mare Caspium', 50.8, 40.9, -72)]
RIVERS = {'Euphrates': (40.25, 34.95, 33), 'Tigris': (44.75, 34.75, -60), 'Halys': None, 'Kızıl': None}


def main():
    countries = json.loads((ROOT / 'data/countries-50m.json').read_text())
    land = path(decode(countries)(countries['objects']['land']['geometries'][0]) if countries['objects']['land']['type'] != 'GeometryCollection'
                else [r for g in countries['objects']['land']['geometries'] for r in decode(countries)(g)], True)
    rv = json.loads((ROOT / 'data/rivers.json').read_text()); dec = decode(rv)
    rivers = path([r for g in rv['objects']['r']['geometries'] if (g.get('properties') or {}).get('r', 9) <= 6 for r in dec(g)], False)
    lakes = path([r for g in rv['objects']['l']['geometries'] for r in dec(g)], True)

    o = [f'<svg class="plate" viewBox="0 0 {W} {H}" role="img" aria-labelledby="plate-t plate-d">',
         '<title id="plate-t">The march of the Ten Thousand, 401 to 400 BCE</title>',
         '<desc id="plate-d">A map from the Aegean to the Persian Gulf. The route runs east from Sardis through Cilicia and Syria, down the Euphrates to Cunaxa near Babylon, then north up the Tigris, through the Carduchian mountains and Armenia, to Mount Theches and Trapezus on the Black Sea. Five numbered markers along it match the five stages of work described below.</desc>',
         '<defs><clipPath id="plate-clip"><rect width="%d" height="%d"/></clipPath></defs>' % (W, H),
         '<g clip-path="url(#plate-clip)">',
         f'<rect width="{W}" height="{H}" class="p-sea"/>']
    # water-lining: rings drawn outward from the coast, the way engravers shaded the sea
    for w in (30, 20, 11):
        o.append(f'<path d="{land}" class="p-wl" stroke-width="{w}"/><path d="{land}" class="p-wl-gap" stroke-width="{w - 2.2}"/>')
    o.append(f'<path d="{land}" class="p-land"/>')
    o.append(f'<path d="{lakes}" class="p-lake"/>')
    o.append(f'<path d="{rivers}" class="p-river"/>')
    grat = []
    for lon in range(30, 55, 5):
        x = xy(lon, 0)[0]; grat.append(f'M{x:.1f} 0V{H}')
    for lat in range(30, 45, 5):
        y = xy(0, lat)[1]; grat.append(f'M0 {y:.1f}H{W}')
    o.append(f'<path d="{"".join(grat)}" class="p-grat"/>')
    for name, lon, lat, rot in SEAS:
        x, y = xy(lon, lat); o.append(f'<text x="{x:.0f}" y="{y:.0f}" class="p-seaname" transform="rotate({rot} {x:.0f} {y:.0f})">{name}</text>')
    for name, lon, lat in REGIONS:
        x, y = xy(lon, lat); o.append(f'<text x="{x:.0f}" y="{y:.0f}" class="p-region">{name}</text>')
    for name, v in RIVERS.items():
        if v: x, y = xy(v[0], v[1]); o.append(f'<text x="{x:.0f}" y="{y:.0f}" class="p-rivername" transform="rotate({v[2]} {x:.0f} {y:.0f})">{name}</text>')
    pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in (xy(*p) for p in ROUTE))
    o.append(f'<polyline points="{pts}" class="p-route-halo"/><polyline points="{pts}" class="p-route"/>')
    for name, lon, lat, dx, dy, anc in STOPS:
        x, y = xy(lon, lat)
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" class="p-stop"/><text x="{x + dx:.0f}" y="{y + dy:.0f}" text-anchor="{anc}" class="p-place">{name}</text>')
    for n, lon, lat, k, dx, dy in WAY:
        x, y = xy(lon, lat); mx, my = x + dx, y + dy
        o.append(f'<g class="p-way" style="--k:var(--{k})"><path d="M{x:.1f} {y:.1f}L{mx:.1f} {my:.1f}"/><circle cx="{mx:.1f}" cy="{my:.1f}" r="15"/><text x="{mx:.1f}" y="{my + 5:.1f}">{n}</text></g>')
    o.append('</g>')
    # neatline ticks and degree labels
    for lon in range(30, 55, 5):
        x = xy(lon, 0)[0]; o.append(f'<text x="{x + 5:.0f}" y="{H - 8}" class="p-deg" text-anchor="start">{lon}°E</text>')
    for lat in range(30, 45, 5):
        y = xy(0, lat)[1]; o.append(f'<text x="{W - 8}" y="{y - 6:.0f}" class="p-deg" text-anchor="end">{lat}°N</text>')
    # scale bar: 100 km and, as Xenophon measured, about 18 parasangs
    km = S / 111.32  # px per km at this latitude scale (north-south)
    x0, y0 = 40, H - 62
    o.append(f'<g class="p-scale"><path d="M{x0} {y0}h{200 * km:.1f}M{x0} {y0 - 5}v10M{x0 + 100 * km:.1f} {y0 - 4}v8M{x0 + 200 * km:.1f} {y0 - 5}v10"/>'
             f'<text x="{x0}" y="{y0 + 22}">200 km, about 36 parasangs</text></g>')
    o.append('</svg>')
    svg = '\n'.join(o)
    page = ROOT / 'web' / 'index.html'
    s = page.read_text(encoding='utf-8')
    s2, n = re.subn(r'<svg class="plate".*?</svg>', lambda m: svg, s, flags=re.S)
    assert n == 1, 'web/index.html needs one <svg class="plate"> placeholder'
    page.write_text(s2, encoding='utf-8')
    print(f'plate {W}x{H}, {len(svg) // 1024} KB')


if __name__ == '__main__':
    main()
