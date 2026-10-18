#!/usr/bin/env python3
"""Developer-only rebuild of offline terrain screens. Requires requirements-data.txt.

No DCS assets are read. Public source files are cached and hashed; generated
rasters cover the three supported planner bounds. Users need no network access.
"""
from pathlib import Path
from io import BytesIO
import array
import concurrent.futures
import hashlib
import json
import math
import os
import sys
import urllib.request

from PIL import Image, ImageDraw
from shapely.geometry import shape, box
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ironanvil.theatres import THEATRES

CACHE=Path(os.environ.get('IRONANVIL_GEOGRAPHY_CACHE',ROOT.parent/'.cache/ironanvil/geography-source'))
OUT=ROOT/'ironanvil/assets/geography'
EXPECTED=json.loads((OUT/'source-sha256.json').read_text()) if (OUT/'source-sha256.json').exists() else {}


def world(lat,lon,zoom):
    size=256*2**zoom
    return (lon+180)/360*size,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*size


def fetch(url):
    path=CACHE/hashlib.sha256(url.encode()).hexdigest()
    refresh='--refresh-sources' in sys.argv
    cached=path.exists() and not refresh
    data=path.read_bytes() if cached else urllib.request.urlopen(url,timeout=40).read()
    if not refresh and url in EXPECTED and hashlib.sha256(data).hexdigest()!=EXPECTED[url]:
        raise ValueError('Source checksum changed; review the data before using --refresh-sources: '+url)
    if not cached:path.write_bytes(data)
    return data


def extent(bounds,zoom):
    w,s,e,n=bounds;left,top=world(n,w,zoom);right,bottom=world(s,e,zoom)
    return math.floor(left),math.floor(top),math.ceil(right),math.ceil(bottom)


def main():
    CACHE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    manifest={}
    geometries={}
    for kind in ('land','lakes','roads'):
        url=f'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_{kind}.geojson'
        data=fetch(url);manifest[url]=hashlib.sha256(data).hexdigest()
        geometries[kind]=[shape(feature['geometry']) for feature in json.loads(data)['features'] if feature['geometry']]
    for key,theatre in THEATRES.items():
        left,top,right,bottom=extent(theatre.bounds,10)
        mask=Image.new('1',(right-left,bottom-top));draw=ImageDraw.Draw(mask)
        region=box(*theatre.bounds)
        for kind in ('land','lakes'):
            for geom in geometries[kind]:
                if not geom.intersects(region):continue
                clipped=geom.intersection(region)
                polygons=list(clipped.geoms) if hasattr(clipped,'geoms') else [clipped]
                for polygon in polygons:
                    if polygon.geom_type!='Polygon':continue
                    def ring(coords):
                        return [(round(x-left),round(y-top)) for x,y in (world(lat,lon,10) for lon,lat in coords)]
                    draw.polygon(ring(polygon.exterior.coords),fill=kind=='land')
                    for interior in polygon.interiors:draw.polygon(ring(interior.coords),fill=kind!='land')
        mask.save(OUT/f'{key}-land.png',optimize=True)
        roads=Image.new('1',mask.size);road_draw=ImageDraw.Draw(roads)
        mpp=156543.033928*math.cos(math.radians((theatre.bounds[1]+theatre.bounds[3])/2))/2**10
        road_width=round(4000/mpp)
        road_count=0
        road_lines=[]
        for geom in geometries['roads']:
            if not geom.intersects(region):continue
            clipped=geom.intersection(region)
            lines=list(clipped.geoms) if hasattr(clipped,'geoms') else [clipped]
            for line in lines:
                if line.geom_type!='LineString':continue
                coords=[(round(x-left),round(y-top)) for x,y in (world(lat,lon,10) for lon,lat in line.coords)]
                if len(coords)>1:
                    road_draw.line(coords,fill=1,width=road_width);road_count+=1;road_lines.append(list(line.coords))
        roads.save(OUT/f'{key}-roads.png',optimize=True)
        l,t,r,b=extent(theatre.bounds,8)
        x0,y0,x1,y1=l//256,t//256,r//256,b//256
        jobs=[(x,y) for x in range(x0,x1+1) for y in range(y0,y1+1)]
        dem=Image.new('I;16',((x1-x0+1)*256,(y1-y0+1)*256))
        def tile(job):
            x,y=job;url=f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/8/{x}/{y}.png'
            data=fetch(url)
            with Image.open(BytesIO(data)) as image:
                image.load();assert image.size==(256,256)
                heights=array.array('H',(r*256+g for r,g,_ in image.convert('RGB').getdata()))
            if sys.byteorder!='little':heights.byteswap()
            return x,y,Image.frombytes('I;16',(256,256),heights.tobytes()),url,hashlib.sha256(data).hexdigest()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for x,y,image,url,digest in pool.map(tile,jobs):
                dem.paste(image,((x-x0)*256,(y-y0)*256));manifest[url]=digest
        dem.save(OUT/f'{key}-height.png',optimize=True)
        # A small pre-rendered relief backdrop adds no work/dependency at runtime.
        w,s,e,n=theatre.bounds
        width,height=1200,round(1200*(bottom-top)/(right-left))
        fx,fy=world(n,w,8);ex,ey=world(s,e,8)
        heights=np.asarray(dem.convert('F').transform((width,height),Image.Transform.EXTENT,
            (fx-x0*256,fy-y0*256,ex-x0*256,ey-y0*256),Image.Resampling.BILINEAR))-32768
        meter_size=156543.033928*math.cos(math.radians((s+n)/2))/2**8*(ex-fx)/width
        gy,gx=np.gradient(heights,meter_size)
        shade=np.clip((1-gx*.6+gy*.6)/np.sqrt(1+gx*gx+gy*gy),.45,1.2)
        levels=[-500,0,200,600,1200,2000,4000,6000]
        colors=[(85,129,115),(109,145,109),(141,157,110),(171,159,115),(181,151,115),(169,148,133),(202,198,186),(241,242,244)]
        rgb=np.stack([np.interp(heights,levels,[c[channel] for c in colors])*shade for channel in range(3)],axis=-1)
        fx,fy=world(n,w,10);ex,ey=world(s,e,10)
        land_pixels=np.asarray(mask.transform((width,height),Image.Transform.EXTENT,
            (fx-left,fy-top,ex-left,ey-top),Image.Resampling.NEAREST),dtype=bool)
        rgb[~land_pixels]=(35,72,96)
        relief=Image.fromarray(np.clip(rgb,0,255).astype('uint8'))
        relief_draw=ImageDraw.Draw(relief)
        for line in road_lines:
            coords=[((x-fx)/(ex-fx)*width,(y-fy)/(ey-fy)*height) for x,y in (world(lat,lon,10) for lon,lat in line)]
            relief_draw.line(coords,fill='#8e6843',width=1)
        relief.save(OUT/f'{key}-relief.png',optimize=True)
        config={'bounds':theatre.bounds,'land':{'zoom':10,'left':left,'top':top},
                'height':{'zoom':8,'left':x0*256,'top':y0*256,'offset':32768},
                'note':'Approximate public terrain, not DCS elevation. Land pixels ~80–130 m; heights ~340–520 m depending on latitude.'}
        (OUT/f'{key}.json').write_text(json.dumps(config,indent=2)+'\n')
        print(key,len(jobs),'elevation tiles',road_count,'road lines',mask.size,flush=True)
    (OUT/'source-sha256.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
