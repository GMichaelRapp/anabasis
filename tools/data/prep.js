const fs=require('fs');
const load=(f,req)=>{const m={exports:{}}; new Function('module','exports','require','define',fs.readFileSync(f,'utf8'))(m,m.exports,req||(()=>({})),undefined); return m.exports;};
const arr=load('d3-array-3.2.5/package/dist/d3-array.min.js'); const geo=load('d3-geo-3.1.2/package/dist/d3-geo.min.js',()=>arr); const topo=load('topojson-client-3.1.0/package/dist/topojson-client.min.js');
const w=JSON.parse(fs.readFileSync('world-atlas-2.0.2/package/countries-50m.json'));
const gs=w.objects.countries.geometries;
const ru=gs.find(g=>g.properties.name==='Russia'), ua=gs.find(g=>g.properties.name==='Ukraine');
const polyFeature=(arcs)=>topo.feature(w,{type:'Polygon',arcs});
const i=ru.arcs.findIndex(p=>geo.geoContains(polyFeature(p),[34.1,44.95]));
console.log('crimea polygon index in Russia:',i, 'ua type', ua.type);
if(i>=0){ const crimea=ru.arcs.splice(i,1)[0]; if(ua.type==='Polygon'){ua.type='MultiPolygon'; ua.arcs=[ua.arcs];} ua.arcs.push(crimea); }
// keep only name + id
gs.forEach(g=>{ g.properties={name:g.properties.name}; });
fs.writeFileSync('countries-50m-anabasis.json', JSON.stringify(w));
const fc=topo.feature(w,w.objects.countries); const at=(x,y)=>fc.features.filter(f=>geo.geoContains(f,[x,y])).map(f=>f.properties.name);
console.log('Simferopol now:',at(34.1,44.95),'Sevastopol:',at(33.52,44.6),'Moscow:',at(37.6,55.75),'Kaliningrad:',at(20.5,54.7));
console.log('size',fs.statSync('countries-50m-anabasis.json').size);
