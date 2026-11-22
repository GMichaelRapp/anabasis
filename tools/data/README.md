# Map and gazetteer data

The files in `data/` are generated once and committed, so the build never needs the network. They are derived from [Natural Earth](https://www.naturalearthdata.com) (public domain) and [world-atlas](https://github.com/topojson/world-atlas) 2.0.2 (ISC). The scripts in this folder record how. They are run with Node.js from a folder holding the downloaded sources.

## data/countries-50m.json

world-atlas 2.0.2 `countries-50m.json` (Natural Earth 1:50m admin-0), processed by `prep.js`:

- The Crimea polygon is moved from Russia to Ukraine, following the internationally recognized border.
- Properties are reduced to `name`.

## data/places.txt

Natural Earth 1:10m *populated places*, one place per line:

```
name|alternate names|admin-1|country|latitude|longitude|population|capital flag
```

Places in Crimea and Sevastopol are listed under Ukraine. About 7,300 places.

## data/admin1.json and data/rivers.json

Built by `admin1.js` with `topojson-server` and `topojson-simplify`:

- **admin1.json** (object `a`): Natural Earth 1:10m admin-1 states and provinces for Ukraine, Russia, Belarus, Moldova, Poland, Georgia, Armenia, Azerbaijan, Iran, Iraq, Syria, Israel, Palestine, Lebanon, Jordan, Saudi Arabia, Yemen, Turkey, China, Taiwan, North and South Korea, Japan, the United States, Afghanistan, Pakistan and India. Properties: `n` (English name), `c` (country), `t` (type). Regions with ISO 3166-2 codes beginning `UA-` (including Crimea and Sevastopol) are assigned to Ukraine. Quantized at 40,000, keeping 3.5 percent of points by weight.
- **rivers.json**: object `r` holds rivers and lake centerlines at scale rank 5 or below worldwide, and 7 or below between 20–62°E and 28–58°N. Object `l` holds Natural Earth 1:50m lakes. Properties: `n` (name), `r` (scale rank). Quantized at 40,000, keeping 8 percent of points.

Polygons are rewound after simplification so that d3-geo reads every ring the right way round. Anabasis repeats this when it loads the data.

After generation, a few names were corrected by hand:

- Ukrainian spellings: Dnieper → Dnipro (river), Odessa → Odesa (oblast).
- Where a city and its surrounding region share a name, the city is suffixed: Kyiv (city), Moscow (city), Minsk (city), Baku and other Azerbaijani municipalities (city), Taiwanese provincial cities (city). Washington → Washington, D.C. The second “Altai Republic” → Altai Krai.
- Kiz?lirmak → Kızılırmak (an encoding error in the source).

Other duplicate names (regions split into several parts) are merged into one shape when Anabasis loads the data.

If you regenerate the data, update the SHA-256 values in `vendor/manifest.json`.
