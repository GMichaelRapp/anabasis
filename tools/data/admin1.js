const fs=require('fs'), path='./topo/node_modules/';
const server=require(path+'topojson-server'), simp=require(path+'topojson-simplify'), client=require(path+'topojson-client');
const KEEP=new Set(['UKR','RUS','BLR','MDA','POL','GEO','ARM','AZE','IRN','IRQ','SYR','ISR','PSX','LBN','JOR','SAU','YEM','TUR','CHN','TWN','PRK','KOR','JPN','USA','AFG','PAK','IND']);
const g=JSON.parse(fs.readFileSync('ne_10m_admin_1_states_provinces.geojson'));
const feats=g.features.filter(f=>KEEP.has(f.properties.adm0_a3)).map(f=>{const p=f.properties; let country=p.admin; if((p.iso_3166_2||'').startsWith('UA-')) country='Ukraine'; return {type:'Feature',geometry:f.geometry,properties:{n:p.name_en||p.name, c:country, t:p.type_en||''}};});
const rv=JSON.parse(fs.readFileSync('ne_10m_rivers_lake_centerlines.geojson'));
const rivers=rv.features.filter(f=>(f.properties.scalerank<=5 || (f.properties.scalerank<=7 && (()=>{const c=JSON.stringify(f.geometry.coordinates).match(/-?\d+\.?\d*/g).map(Number); const lon=c[0],lat=c[1]; return lon>20&&lon<62&&lat>28&&lat<58;})())) && f.properties.featurecla!=='Lake Centerline (Intermittent)').map(f=>({type:'Feature',geometry:f.geometry,properties:{n:f.properties.name_en||f.properties.name||'',r:f.properties.scalerank}}));
const lk=JSON.parse(fs.readFileSync('ne_50m_lakes.geojson'));
const lakes=lk.features.map(f=>({type:'Feature',geometry:f.geometry,properties:{n:f.properties.name||''}}));
const GEO=(()=>{const m={exports:{}}; const arr=(()=>{const m2={exports:{}}; new Function('module','exports','define',fs.readFileSync('d3-array-3.2.5/package/dist/d3-array.min.js','utf8'))(m2,m2.exports); return m2.exports})(); new Function('module','exports','require','define',fs.readFileSync('d3-geo-3.1.2/package/dist/d3-geo.min.js','utf8'))(m,m.exports,()=>arr); return m.exports})();
function rewind(f){ const fix=poly=>{ if(GEO.geoArea({type:'Polygon',coordinates:poly})>2*Math.PI) poly.forEach(r=>r.reverse()); }; const g=f.geometry; if(!g) return f; if(g.type==='Polygon') fix(g.coordinates); if(g.type==='MultiPolygon') g.coordinates.forEach(fix); return f; }
feats.forEach(rewind); lakes.forEach(rewind);
console.log('admin1',feats.length,'rivers',rivers.length,'lakes',lakes.length);
function build(objs, q, keep){ let t=server.topology(objs, q); t=simp.presimplify(t); t=simp.simplify(t, simp.quantile(t, keep)); t=simp.filter(t, simp.filterWeight(t, 0)); return t; }
const t1=build({a:{type:'FeatureCollection',features:feats}}, 4e4, 0.035);
const t2=build({r:{type:'FeatureCollection',features:rivers}, l:{type:'FeatureCollection',features:lakes.filter(f=>GEO.geoArea(f)>4e-6)}}, 4e4, 0.08);
fs.writeFileSync('admin1.json', JSON.stringify(t1)); fs.writeFileSync('rivers.json', JSON.stringify(t2));
console.log('admin1.json', fs.statSync('admin1.json').size, 'rivers.json', fs.statSync('rivers.json').size);
const fc=client.feature(t1,t1.objects.a); fc.features.forEach(f=>{ const g=f.geometry; if(!g) return; const polys=g.type==='Polygon'?[g.coordinates]:g.type==='MultiPolygon'?g.coordinates:[]; polys.forEach(p=>{ if(GEO.geoArea({type:'Polygon',coordinates:p})>2*Math.PI) p.forEach(r=>r.reverse()); }); }); const geo=(()=>{const m={exports:{}}; const arr=(()=>{const m2={exports:{}}; new Function('module','exports','define',fs.readFileSync('d3-array-3.2.5/package/dist/d3-array.min.js','utf8'))(m2,m2.exports); return m2.exports})(); new Function('module','exports','require','define',fs.readFileSync('d3-geo-3.1.2/package/dist/d3-geo.min.js','utf8'))(m,m.exports,()=>arr); return m.exports})();
const at=(x,y)=>fc.features.filter(f=>geo.geoContains(f,[x,y])).map(f=>f.properties.c+'/'+f.properties.n);
console.log('Simferopol',at(34.1,44.95),'Kharkiv',at(36.23,49.99),'Bakhmut',at(38.0,48.6),'Taipei',at(121.56,25.04),'Clovis NM',at(-103.2,34.4),'Damascus',at(36.3,33.5));
const names=new Set(rivers.map(f=>f.properties.n)); console.log(['Dnieper','Dnipro','Don','Volga','Euphrates','Tigris','Yangtze','Rio Grande','Danube','Pecos'].map(n=>n+':'+names.has(n)).join(' '));
