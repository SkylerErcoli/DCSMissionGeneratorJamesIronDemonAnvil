#!/usr/bin/env python3
"""Fast planning diversity report, without building missions or kneeboards."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw,ImageFont
from ironanvil.geography import plan_scenario
from ironanvil.model import MissionOptions,resolve_aircraft
from ironanvil.theatres import THEATRES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=300)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    rows=[];failures=[];summary={}
    for key,theatre in THEATRES.items():
        terrain=theatre.terrain();aircraft=resolve_aircraft('FA_18C_hornet')
        for seed in range(args.count):
            for mission,operation in [('facility','classic'),('facility','rolling_thunder')]:
                options=MissionOptions(map=key,mission=mission,operation=operation,recovery='home_or_alternate',seed=seed)
                try:
                    plan=plan_scenario(options,theatre,terrain,aircraft,random.Random(seed))
                    loc=plan.target.latlng();home=plan.home.position.latlng()
                    rows.append({'map':key,'classic':operation=='classic','seed':seed,'home':plan.home.name,
                        'home_lat':home.lat,'home_lon':home.lng,'lat':loc.lat,'lon':loc.lng,
                        'heading':plan.metadata['heading_grid'],'distance_km':plan.metadata['distance_km']})
                except ValueError as error:failures.append({'map':key,'seed':seed,'operation':operation,'error':str(error)})
        for classic in (True,False):
            values=[row for row in rows if row['map']==key and row['classic']==classic]
            summary[key+'/'+('classic' if classic else 'operation')]={
                'plans':len(values),'departure_count':len({r['home'] for r in values}),
                'unique_targets':len({(round(r['lat'],5),round(r['lon'],5)) for r in values}),
                'heading_sectors':dict(sorted(Counter(int(r['heading']//45) for r in values).items())),
                'target_half_degree_cells':len({(int(r['lat']*2),int(r['lon']*2)) for r in values})}
    (args.output/'diversity.json').write_text(json.dumps({'summary':summary,'failures':failures,'plans':rows},indent=2))
    baseline=json.loads(args.baseline.read_text()) if args.baseline else []
    image=Image.new('RGB',(1500,1080),'#111923');draw=ImageDraw.Draw(image)
    title=ImageFont.load_default(size=25);font=ImageFont.load_default(size=17)
    draw.text((24,16),'Automatic mission geography — 300 seeds per map and mode',font=title,fill='white')
    for col,(key,theatre) in enumerate(THEATRES.items()):
        w,s,e,n=theatre.bounds
        for row,values in enumerate((baseline,rows)):
            x0,y0=20+col*495,88+row*485;x1,y1=x0+465,y0+410
            draw.rectangle((x0,y0,x1,y1),fill='#202936',outline='#48566a')
            selected=[r for r in values if r['map']==key and r['classic']]
            for item in selected:
                x=x0+(item['lon']-w)/(e-w)*(x1-x0);y=y1-(item['lat']-s)/(n-s)*(y1-y0)
                draw.ellipse((x-2,y-2,x+2,y+2),fill='#ef9c47')
                if 'home_lon' in item:
                    hx=x0+(item['home_lon']-w)/(e-w)*(x1-x0);hy=y1-(item['home_lat']-s)/(n-s)*(y1-y0)
                    draw.ellipse((hx-2,hy-2,hx+2,hy+2),fill='#60b8e8')
            label=key.title()+(' — before' if row==0 else ' — after')
            draw.text((x0,y0-27),label,font=title,fill='white')
            draw.text((x0,y1+6),f'{len(selected)} plans · {len({r["home"] for r in selected})} departure bases',font=font,fill='#b0bfd0')
    draw.text((20,1050),'Orange: targets · Blue: departures (after) · Geographic scatter only; no terrain chart shown.',font=font,fill='#b0bfd0')
    image.save(args.output/'diversity.png')
    print(json.dumps({'summary':summary,'failures':len(failures)},indent=2))
    return bool(failures)


if __name__=='__main__':raise SystemExit(main())
