"""Seeded scenario planning and offline public terrain screening.

The data rejects obvious water, woodland and steep terrain; it cannot certify
the finer DCS mesh, buildings, trees or roads. Explicit pins remain exact.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

from PIL import Image
from dcs import mapping

from .airfields import _compatibility_error, select_airport

DATA=Path(__file__).with_name('assets')/'geography'


def world(lat,lon,zoom):
    size=256*2**zoom
    return (lon+180)/360*size,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*size


@lru_cache(maxsize=1) # The desktop plans one theatre at a time; release old rasters.
def terrain_data(key):
    metadata=json.loads((DATA/f'{key}.json').read_text())
    images=[]
    for kind in ('land','height'):
        with Image.open(DATA/f'{key}-{kind}.png') as image:
            image.load();images.append(image.copy())
    return metadata,*images


def public_land(theatre,lat,lon):
    if not theatre.contains(lat,lon):return False
    metadata,land,_=terrain_data(theatre.key)
    info=metadata['land'];x,y=world(lat,lon,info['zoom']);x,y=int(x-info['left']),int(y-info['top'])
    return 0<=x<land.width and 0<=y<land.height and bool(land.getpixel((x,y)))


def height_at(theatre,lat,lon):
    if not theatre.contains(lat,lon):return None
    metadata,_,image=terrain_data(theatre.key);info=metadata['height']
    x,y=world(lat,lon,info['zoom']);x,y=x-info['left']-.5,y-info['top']-.5
    ix,iy=math.floor(x),math.floor(y);dx,dy=x-ix,y-iy
    if not (0<=ix<image.width-1 and 0<=iy<image.height-1):return None
    a,b=image.getpixel((ix,iy)),image.getpixel((ix+1,iy))
    c,d=image.getpixel((ix,iy+1)),image.getpixel((ix+1,iy+1))
    return ((a*(1-dx)+b*dx)*(1-dy)+(c*(1-dx)+d*dx)*dy)-info['offset']


@lru_cache(maxsize=1)
def road_mask(key):
    with Image.open(DATA/f'{key}-roads.png') as image:
        image.load();return image.copy()


def near_road(point,theatre):
    loc=point.latlng()
    if not theatre.contains(loc.lat,loc.lng):return False
    info=terrain_data(theatre.key)[0]['land'];image=road_mask(theatre.key)
    x,y=world(loc.lat,loc.lng,info['zoom']);x,y=int(x-info['left']),int(y-info['top'])
    return 0<=x<image.width and 0<=y<image.height and bool(image.getpixel((x,y)))


@lru_cache(maxsize=1)
def woodland_data(key):
    metadata=json.loads((DATA/'woodland.json').read_text())
    info=metadata['maps'][key]
    with Image.open(DATA/f'{key}-forest.png') as image:
        image.load();mask=image.copy()
    if mask.mode!='1' or list(mask.size)!=info['size']:
        raise ValueError('The bundled woodland data is invalid. Download a fresh copy of Iron Anvil.')
    return info,mask,metadata['clearance_m']


def woodland_clear(point,theatre,*,footprint=0):
    """Reject any mapped trees across a site's bounding box plus clearance.

    Scan all cells, not just the centre/perimeter: a wooded patch can sit
    between sample points. Unknown/out-of-bounds cells fail closed. Fixed DCS
    airfield spawns and routes through forests are not relocation candidates.
    """
    location=point.latlng()
    info,mask,margin=woodland_data(theatre.key)
    west,south,east,north=info['bounds'];step=info['step_degrees']
    radius=max(0,footprint)+margin
    dy=radius/110574
    dx=radius/(111320*math.cos(math.radians(location.lat)))
    left=(location.lng-dx-west)/step;right=(location.lng+dx-west)/step
    top=(north-location.lat-dy)/step;bottom=(north-location.lat+dy)/step
    if left<0 or top<0 or right>=mask.width or bottom>=mask.height:return False
    rectangle=(math.floor(left),math.floor(top),math.floor(right)+1,math.floor(bottom)+1)
    return mask.crop(rectangle).getbbox() is None


def suitable_ground(point,theatre,*,footprint=220,airports=(),screen_woodland=True):
    if screen_woodland and not woodland_clear(point,theatre,footprint=footprint):return False
    heights=[]
    for bearing,distance in [(0,0)]+[(bearing,footprint) for bearing in range(0,360,45)]:
        location=point.point_from_heading(bearing,distance).latlng()
        if not public_land(theatre,location.lat,location.lng):return False
        height=height_at(theatre,location.lat,location.lng)
        if height is None or height>1800:return False
        heights.append(height)
    if max(heights)-min(heights)>25:return False
    # Reserve space around runways/helipads rather than placing objectives on them.
    return all(point.distance_to_point(airport.position)>=2500 for airport in airports)


def distance_band(aircraft,pace):
    nominal=(10000,22000,38000) if aircraft.helicopter else (28000,60000,100000)
    distance=nominal[('compact','standard','extended').index(pace)]
    return distance*.8,distance*1.2


def region_order(airports,rng):
    """Balance half-degree cells before airports: dense catalogues get no bonus."""
    cells={}
    for airport in sorted(airports,key=lambda airport:airport.id):
        loc=airport.position.latlng();key=(math.floor(loc.lat*2),math.floor(loc.lng*2))
        cells.setdefault(key,[]).append(airport)
    keys=sorted(cells);rng.shuffle(keys)
    for key in keys:rng.shuffle(cells[key])
    while keys:
        for key in list(keys):
            yield cells[key].pop()
            if not cells[key]:keys.remove(key)


def sample_target(home,theatre,aircraft,pace,rng,airports,*,ground=True,accept=None,footprint=220,road=False,distance_scale=1):
    low,high=distance_band(aircraft,pace)
    low*=distance_scale;high*=distance_scale
    # Stratified directions plus independent angles; no ordered compass fallback.
    sectors=list(range(24));rng.shuffle(sectors)
    for _ in range(6):
        for sector in sectors:
            heading=(sector+rng.random())*15
            distance=math.sqrt(rng.uniform(low*low,high*high))
            point=home.position.point_from_heading(heading,distance)
            loc=point.latlng()
            if not theatre.contains(loc.lat,loc.lng):continue
            if ground and not suitable_ground(point,theatre,airports=airports,footprint=footprint):continue
            if road and not near_road(point,theatre):continue
            if not ground and not theatre.is_land(loc.lat,loc.lng):continue
            if accept and not accept(point):continue
            return point
        rng.shuffle(sectors)
    return None


@dataclass
class Scenario:
    home: object
    target: object
    alternate: object|None
    ownership: dict
    metadata: dict
    sites: dict


def plan_scenario(options,theatre,terrain,aircraft,rng):
    airports=list(terrain.airports.values())
    compatible=[airport for airport in airports if not _compatibility_error(airport,aircraft,options.clients,options.start)
                and theatre.contains(airport.position.latlng().lat,airport.position.latlng().lng)]
    pinned=options.target_lat is not None
    target=mapping.Point.from_latlng(mapping.LatLng(options.target_lat,options.target_lon),terrain) if pinned else None
    if options.departure_airport:
        homes=[select_airport(terrain,theatre,target,aircraft,options.clients,options.start,options.departure_airport)]
    elif pinned:
        homes=sorted(compatible,key=lambda airport:airport.position.distance_to_point(target))
    else:homes=region_order(compatible,rng)
    selected=None
    sites={}
    # Automatic plans prefer a nearby alternate. An explicitly requested base
    # can be isolated by coast/mountains; retain it and explain a longer recovery.
    alternate_floor=240000 if options.departure_airport else 120000
    for home in homes:
        def related(point):
            if options.recovery=='home_or_alternate':
                dx,dz=point.x-home.position.x,point.y-home.position.y
                length_squared=dx*dx+dz*dz
                maximum=max(alternate_floor,math.sqrt(length_squared)*1.25)
                if not any(airport.id!=home.id and airport.position.distance_to_point(home.position)<=maximum and
                    ((airport.position.x-home.position.x)*dx+(airport.position.y-home.position.y)*dz)<length_squared*.45
                    for airport in compatible):return False
            if options.operation=='classic' and options.mission!='convoy':return True
            from .operations import _separate_site
            try:
                if options.operation=='classic':
                    destination=_separate_site(point,home,theatre,rng,distance=12000,road=True,screen_woodland=not pinned)
                    sites.clear();sites['destination']=destination;return True
                separation={'compact':2400,'standard':3800,'extended':6000}[options.pace]
                secondary=_separate_site(point,home,theatre,rng,distance=separation,screen_woodland=not pinned)
                planned={'secondary':secondary}
                if options.operation=='rolling_thunder':
                    planned['destination']=_separate_site(point,home,theatre,rng,distance=7500,excluded=(secondary,),road=True,screen_woodland=not pinned)
                if options.enemy_response:
                    planned['staging']=_separate_site(point,home,theatre,rng,distance=9000,excluded=tuple(planned.values()),road=True,screen_woodland=not pinned)
                sites.clear();sites.update(planned)
                return True
            except ValueError:return False
        if pinned:
            if not related(target):
                if not options.departure_airport:continue
                raise ValueError('The pinned target/departure cannot fit the operation and a safe alternate. Try home-only recovery, another pin or a classic mission.')
            chosen=target
        else:
            chosen=sample_target(home,theatre,aircraft,options.pace,rng,airports,ground=options.mission!='cap' or options.air_defenses,
                                 accept=related,footprint=450 if options.mission=='line' else 220,
                                 road=options.mission=='convoy' or options.operation=='rolling_thunder')
            # Honor an explicitly chosen coastal/wooded departure without
            # weakening screening. Automatic departures retain their distance
            # band and can try another airport instead.
            if chosen is None and options.departure_airport:
                for scale in (1.5,2,3):
                    chosen=sample_target(home,theatre,aircraft,options.pace,rng,airports,
                        ground=options.mission!='cap' or options.air_defenses,accept=related,
                        footprint=450 if options.mission=='line' else 220,
                        road=options.mission=='convoy' or options.operation=='rolling_thunder',distance_scale=scale)
                    if chosen is not None:break
        if chosen is not None:selected=(home,chosen);break
    if selected is None:
        raise ValueError('No suitable target for this departure and distance. Try another airfield or distance, or pin a target.')
    home,target=selected
    # A local front halfway to the objective gives every generated direction a
    # coherent friendly rear, rather than leaving the old fixed blue/red bases.
    dx,dz=target.x-home.position.x,target.y-home.position.y
    length=math.hypot(dx,dz)
    def progress(airport):
        return ((airport.position.x-home.position.x)*dx+(airport.position.y-home.position.y)*dz)/max(length,1)
    ownership={airport.id:('blue' if progress(airport)<length*.45 else 'red') for airport in airports}
    alternate=None
    if options.recovery=='home_or_alternate':
        candidates=[airport for airport in compatible if airport.id!=home.id and progress(airport)<length*.45
                    and airport.position.distance_to_point(home.position)<=max(alternate_floor,length*1.25)]
        if not candidates:raise ValueError('No compatible nearby friendly alternate is available. Choose home-base recovery or another departure.')
        alternate=min(candidates,key=lambda airport:airport.position.distance_to_point(home.position))
        ownership[alternate.id]='blue'
    ownership[home.id]='blue'
    location=target.latlng()
    notes=[]
    if not pinned and length>distance_band(aircraft,options.pace)[1]:
        notes.append(f'Woodland/terrain screening needs a longer sortie from {home.name}: {length/1000:.0f} km to the target. Choose another departure for a closer target.')
    if alternate and home.position.distance_to_point(alternate.position)>120000:
        notes.append(f'This selected departure needs a longer friendly alternate: {alternate.name}, '
                     f'{home.position.distance_to_point(alternate.position)/1000:.0f} km from home. Choose home-only recovery or another departure for a closer recovery plan.')
    if pinned and (options.mission!='cap' or options.air_defenses) and not suitable_ground(target,theatre,airports=airports):
        notes.append('Pinned target retained exactly; public terrain screening flags nearby woodland, water, elevation, slope or an airfield. Move the pin or use automatic placement for screened ground sites.')
    info={'algorithm':3,'selection':'pinned' if pinned else 'automatic','heading_grid':round(home.position.heading_between_point(target),1),
          'distance_km':round(length/1000,2),'target_height_m':round(height_at(theatre,location.lat,location.lng) or 0),
          'terrain':'Offline land/lakes/roads, elevation and ESA WorldCover woodland screening; DCS terrain, trees and roads remain authoritative.',
          'notes':notes}
    return Scenario(home,target,alternate,ownership,info,sites)


def hostile_air_spawn(home,target,theatre,rng,*,distance):
    away=home.position.heading_between_point(target)
    turns=list(range(-150,181,30));rng.shuffle(turns)
    dx,dz=target.x-home.position.x,target.y-home.position.y
    for scale in (1,.75,.5):
        for turn in turns:
            point=target.point_from_heading(away+turn,distance*scale)
            loc=point.latlng()
            if not theatre.contains(loc.lat,loc.lng):continue
            if (point.x-home.position.x)*dx+(point.y-home.position.y)*dz<(dx*dx+dz*dz)*.7:continue
            return point
    raise ValueError('No hostile air staging space inside this map. Move the target inland or disable enemy fighters.')


def support_plan(home,target,theatre):
    bearing=home.position.heading_between_point(target)
    distance=home.position.distance_to_point(target)
    dx,dz=target.x-home.position.x,target.y-home.position.y
    for fraction in (.25,.1,0,-.15):
        anchor=home.position.point_from_heading(bearing,min(30000,distance*fraction))
        for turn in (90,-90):
            heading=(bearing+turn)%360
            awacs=anchor.point_from_heading(heading+90,10000)
            valid=True
            for start in (anchor,awacs):
                for point in (start,start.point_from_heading(heading+180,8000),start.point_from_heading(heading,25000)):
                    loc=point.latlng()
                    if (not theatre.contains(loc.lat,loc.lng) or
                        (point.x-home.position.x)*dx+(point.y-home.position.y)*dz>(dx*dx+dz*dz)*.45):valid=False
            if valid:return anchor,heading,awacs
    raise ValueError('No support orbit fits behind this departure inside the map. Choose another base or disable support.')
