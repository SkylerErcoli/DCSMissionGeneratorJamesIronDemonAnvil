"""Local, shareable mission briefings and a schematic DCS kneeboard page."""
from __future__ import annotations

import base64
from html import escape
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from . import APP_NAME
from .operations import OPERATION_LABELS, operation_briefing


def mission_help_lines(metadata):
    """Short action-based briefing shared with the in-mission radio menu."""
    options=metadata['options'];operation=metadata['runtime'].get('operation')
    lines=[title(metadata)]
    if operation:
        for goal in operation['objectives']:
            kind='supply trucks' if goal.get('units') else 'objective structures'
            lines.append(('REQUIRED: ' if goal['required'] else 'OPTIONAL: ')+
                f"Disable {goal['threshold']} {kind} at {goal['title']}.")
        lines.append('Guards, escorts and scenery are not required cleanup targets.')
        if operation.get('response'):
            effect='delays the ground response by six minutes' if operation['id']=='broken_relay' else 'cancels the ground response'
            lines.append('The optional objective '+effect+' if completed before dispatch.')
    elif options['mission']=='cap':
        lines.append('Defeat the enemy fighter flights. They activate after a client takes off.' if options['enemy_cap'] else
                     'Fly airborne within 25 km of the patrol area for five minutes. No enemy fighters are enabled.')
    else:
        lines.append({'facility':'Destroy the installation and its supporting sites.',
            'line':'Destroy the enemy troops and vehicles in the fortified positions.',
            'convoy':'Destroy the moving convoy. Request Target position / mark for its current location.',
            'sead':'Destroy the enemy air defenses.' if options['air_defenses'] else
                'Air defenses are off. Destroy the command and support vehicles instead.'}[options['mission']])
    if metadata.get('intelligence'):
        lines.append('Search: stay airborne inside the briefed area for 45 continuous seconds, then request Recon check-in.')
    if options['mission']!='cap':
        lines.append('Need a visual cue? F10 Target assistance > Smoke target (orange). An airborne teammate must be within 15 km; shared five-minute cooldown. Confirm search intelligence first.')
    lines.append('RECOVERY: land every surviving participating aircraft at '+metadata['runtime']['recovery_label']+'.')
    if options['allow_withdrawal']:lines.append('Need to leave early? Agree over comms, then Team withdrawal > Propose and Confirm. Recover everyone for partial credit.')
    lines.append('Flight radio: 251 MHz AM.'+(' Tanker: 251.5 MHz / TACAN 11Y.' if metadata['tanker'] else '')+
                 (' AWACS: 252 MHz.' if options['awacs'] else ''))
    if metadata.get('loadout',{}).get('warning'):lines.append(metadata['loadout']['warning'])
    return lines


def title(metadata):
    options=metadata['options']
    return OPERATION_LABELS.get(options['operation'],options['mission'].title()) if options['operation']!='classic' else options['mission'].title()+' mission'


def summary_lines(metadata):
    options=metadata['options'];route=metadata['route_summary'];operation=metadata['runtime'].get('operation')
    intelligence=metadata.get('intelligence')
    lines=[f"{options['map'].title()} | {options['clients']} pilots | {options['aircraft']}",
           f"Home: {metadata['home_airport']} | Flight: 251 MHz AM",
           f"Weather: {metadata['resolved_weather']} | Start: {options['start']} | Time: {options['time_of_day']}",
           f"Home to {'search area' if intelligence else 'target'}: {route['one_way_km']:.1f} km / {route['one_way_km']/1.852:.1f} NM",
           f"Cruise-only round trip: ~{route['cruise_round_trip_minutes']} min; excludes startup, combat and recovery.",
           f"Enemy CAP: {'on' if options['enemy_cap'] else 'off'} | Air defenses: {'on' if options['air_defenses'] else 'off'}",
           f"Replay seed: {options['seed']}"]
    if options['tanker'] and metadata['tanker']:lines.append('Tanker: 251.5 MHz AM | TACAN 11Y TEX')
    if options['awacs']:lines.append('AWACS: 252 MHz AM')
    if metadata.get('alternate_airport'):
        lines.append('Approved recovery: '+metadata['home_airport']+' or '+metadata['alternate_airport']+'. F10 Vector alternate is available.')
    if operation:
        for index, goal in enumerate(operation['objectives']):
            site=metadata['facility_sites'][index]
            total=len(goal.get('statics', []))+len(goal.get('units', []))
            kind='supply trucks' if goal.get('units') else 'objective structures'
            location='Coordinates unconfirmed.' if intelligence else f"{site['latitude']:.5f}, {site['longitude']:.5f}"
            lines.append(('REQUIRED: ' if goal['required'] else 'BONUS: ')+goal['title']+
                         f" - disable {goal['threshold']} of {total} {kind}. {location}")
        if operation.get('convoy'):
            lines.append('Convoy departs after takeoff. F10 follows its live position; stopping it before delivery earns 150 bonus points.')
        if operation.get('response'):
            lines.append('One staged ground response; first objective damage raises the alarm.')
            lines.append('Bonus before dispatch '+('delays response by six minutes.' if operation['id']=='broken_relay' else 'cancels the ground response.'))
        else:lines.append('Ground response disabled; bonus remains optional.')
    else:
        if not intelligence:lines.append(f"Main target: {metadata['target_lat']:.5f}, {metadata['target_lon']:.5f}")
    if intelligence:
        lines.append(f"Search center: {intelligence['latitude']:.5f}, {intelligence['longitude']:.5f}. Radius {intelligence['radius']/1000:g} km.")
        lines.append('Stay airborne inside the area for 45 seconds, then use F10 Recon check-in for shared updated coordinates. No special sensor required.')
    lines.append('F10 > Iron Anvil: status, target marks, bearing/range and vector home.')
    lines.append('Complete the required goal and recover all surviving teammates at an approved base.')
    if options.get('allow_withdrawal'):
        lines.append('Team withdrawal: Propose, agree over comms, then Confirm within 30 seconds. Recover survivors for a partial debrief.')
    return lines


def diagram_label_boxes(markers,sizes,bounds,protected=()):
    """Place short schematic callouts without covering nearby labels or dots."""
    left_edge,top_edge,right_edge,bottom_edge=bounds
    occupied=list(protected)+[(x-9,y-9,x+9,y+9) for x,y in markers]
    boxes=[]
    def overlap(box,other):
        return box[0]<other[2]+4 and box[2]>other[0]-4 and box[1]<other[3]+4 and box[3]>other[1]-4
    for (x,y),(width,height) in zip(markers,sizes):
        candidates=[]
        for row in range(12):
            gap=12+row*(height+9)
            for left in (x+13,x-width-13):
                for top in (y-gap-height,y+gap):
                    left=max(left_edge,min(right_edge-width,left))
                    top=max(top_edge,min(bottom_edge-height,top))
                    box=(left,top,left+width,top+height)
                    score=sum(overlap(box,other) for other in occupied)
                    candidates.append((score,box))
                    if not score:break
                if candidates[-1][0]==0:break
            if candidates[-1][0]==0:break
        _,box=min(candidates,key=lambda candidate:candidate[0])
        boxes.append(box);occupied.append(box)
    return boxes


def kneeboard_png(metadata):
    image=Image.new('RGB',(1000,1440),'#f3f1e8');draw=ImageDraw.Draw(image)
    font=ImageFont.load_default(size=23);small=ImageFont.load_default(size=20);heading=ImageFont.load_default(size=34)
    draw.rectangle((0,0,1000,112),fill='#172b40')
    draw.text((35,22),APP_NAME,fill='white',font=heading)
    draw.text((35,70),title(metadata),fill='#b9def3',font=font)
    y=130
    def text(value,face=font,color='#172b40'):
        nonlocal y
        words=str(value).split();line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if face.getlength(candidate)>930 and line:
                draw.text((35,y),line,font=face,fill=color);y+=29 if face==font else 24;line=word
            else:line=candidate
        if line:draw.text((35,y),line,font=face,fill=color);y+=29 if face==font else 24
    lines=summary_lines(metadata)
    for value in lines[:9]:text(value)
    y+=10;top=y;bottom=top+365
    draw.rectangle((35,top,965,bottom),fill='#e0e6e5',outline='#829394',width=2)
    public_points=metadata['planner']['points']
    palette={'home':'#21679e','alternate':'#21679e','required':'#b54630','bonus':'#aa790b',
             'response':'#714b8e','search':'#aa790b','delivery':'#714b8e'}
    labels={'home':'HOME','alternate':'ALTERNATE','required':'MAIN','response':'RESERVES','search':'SEARCH AREA','delivery':'DELIVERY'}
    points=[(labels.get(p['role'],p['label']),p,palette[p['role']]) for p in public_points]
    home=next(p for p in public_points if p['role']=='home')
    target=next(p for p in public_points if p['role'] in ('required','search'))
    low_x=min(p['x'] for _,p,_ in points);high_x=max(p['x'] for _,p,_ in points)
    low_z=min(p['z'] for _,p,_ in points);high_z=max(p['z'] for _,p,_ in points)
    scale=min(750/max(high_z-low_z,1000),225/max(high_x-low_x,1000))
    def project(point):
        return (500+(point['z']-(low_z+high_z)/2)*scale,
                (top+bottom)/2-(point['x']-(low_x+high_x)/2)*scale)
    draw.line((*project(home),*project(target)),fill='#5d7a88',width=3)
    if metadata.get('intelligence'):
        x,z=project(target);radius=metadata['intelligence']['radius']*scale
        draw.ellipse((x-radius,z-radius,x+radius,z+radius),outline='#aa790b',width=3)
    draw.text((52,top+14),'ROUTE SCHEMATIC - terrain and obstacles not shown',fill='#41575d',font=small)
    markers=[project(point) for _,point,_ in points]
    sizes=[draw.textbbox((0,0),label,font=small) for label,_,_ in points]
    boxes=diagram_label_boxes(markers,[(box[2]-box[0],box[3]-box[1]) for box in sizes],
        (45,top+51,955,bottom-8),protected=[(850,top+43,940,top+116)])
    for (x,z),(_,_,color) in zip(markers,points):
        draw.ellipse((x-7,z-7,x+7,z+7),fill=color)
    for (label,point,color),(x,z),box,size in zip(points,markers,boxes,sizes):
        end_x=max(box[0],min(box[2],x));end_z=max(box[1],min(box[3],z))
        draw.line((x,z,end_x,end_z),fill=color,width=1)
        draw.rectangle(box,fill='#e0e6e5')
        draw.text((box[0]-size[0],box[1]-size[1]),label,font=small,fill=color)
    draw.text((860,top+43),'Grid N',font=small,fill='#41575d')
    draw.line((895,top+108,895,top+75),fill='#41575d',width=3)
    draw.polygon([(895,top+68),(888,top+80),(902,top+80)],fill='#41575d')
    y=bottom+17
    for value in lines[9:]:text(value,small)
    text('Check placement and loadouts in DCS Mission Editor. Experimental: in-simulator validation is pending.',small,'#695746')
    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()


def briefing_html(metadata,png):
    operation=metadata['runtime'].get('operation')
    heading=escape(title(metadata));items=''.join('<li>'+escape(line)+'</li>' for line in summary_lines(metadata))
    detail='<pre>'+escape(operation_briefing(operation))+'</pre>' if operation else ''
    data=base64.b64encode(png).decode('ascii')
    task=''.join('<li>'+escape(line)+'</li>' for line in mission_help_lines(metadata))
    stores=''.join(f"<li>Station {store['station']}: {escape(store['name'])}</li>" for store in metadata.get('loadout',{}).get('stores',[]))
    loadout='<ul>'+stores+'</ul>' if stores else '<p>'+escape(metadata.get('loadout',{}).get('warning') or 'Review weapons in DCS before flying.')+'</p>'
    navigation=metadata['navigation']
    bases=''.join('<li>'+escape(base['role']+': '+base['name']+' | '+
        (' / '.join(base['runways']) if base['runways'] else 'Helipad / no runway')+' | '+
        (' | '.join(base['radios']) or 'No catalogue ATC frequency'))+'</li>' for base in navigation['airports'])
    rows=''.join('<tr><td>'+escape(point['role'].upper()+': '+point['label'])+'</td><td>'+
        '<br>'.join(escape(label+': '+point['coordinates'][key]) for label,key in
                     (('Decimal','decimal'),('DDM','ddm'),('DMS','dms')))+'</td></tr>' for point in navigation['points'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading} - Iron Anvil Experimental</title><style>
body{{margin:0;background:#111923;color:#edf3fa;font:17px/1.6 system-ui,sans-serif}}main{{max-width:980px;margin:auto;padding:28px}}
h1{{line-height:1.2}}li{{margin:9px 0}}pre{{white-space:pre-wrap;font:inherit;background:#202936;padding:22px;border-radius:10px}}
img{{max-width:100%;height:auto;border-radius:8px}}.muted{{color:#b0bfd0}}@media print{{body{{background:white;color:black}}pre{{background:#eee}}}}
table{{width:100%;border-collapse:collapse}}td{{padding:12px;border-bottom:1px solid #48566a;vertical-align:top}}td:last-child{{font-variant-numeric:tabular-nums}}@media(max-width:650px){{td{{display:block}}}}
</style><main><p class="muted">IRON ANVIL EXPERIMENTAL - COOPERATIVE BRIEFING</p><h1>{heading}</h1>
<h2>Your job</h2><ul>{task}</ul><h2>Navigation and radios</h2><ul>{bases}</ul><table><tbody>{rows}</tbody></table><p class="muted">{escape(navigation['note'])}</p><details><summary>Weapons and stores aboard</summary>{loadout}</details><details><summary>Flight details and full operation briefing</summary><ul>{items}</ul>{detail}</details><h2>Kneeboard and route schematic</h2><p>The mission includes this schematic and a separate navigation/radio kneeboard page.</p>
<img alt="Mission kneeboard with objectives, communications and route schematic" src="data:image/png;base64,{data}">
<p class="muted">Generated locally. No account or online service is required. Check the mission in DCS before flying.</p></main></html>'''


def navigation_png(metadata):
    """A second uncluttered page; hidden intelligence never enters this renderer."""
    image=Image.new('RGB',(1000,1440),'#f3f1e8');draw=ImageDraw.Draw(image)
    heading=ImageFont.load_default(size=32);font=ImageFont.load_default(size=21)
    small=ImageFont.load_default(size=19);y=128
    draw.rectangle((0,0,1000,105),fill='#172b40')
    draw.text((35,23),'NAVIGATION AND RADIOS',font=heading,fill='white')
    draw.text((35,67),title(metadata),font=font,fill='#b9def3')

    def text(value,face=font,color='#172b40'):
        nonlocal y
        line=''
        for word in value.split():
            trial=(line+' '+word).strip()
            if face.getlength(trial)>925 and line:
                draw.text((35,y),line,font=face,fill=color);y+=27;line=word
            else:line=trial
        if line:draw.text((35,y),line,font=face,fill=color);y+=27

    text('Flight: 251 MHz AM'+(' | Tanker: 251.5 MHz / TACAN 11Y TEX' if metadata['tanker'] else '')+
         (' | AWACS: 252 MHz' if metadata['options']['awacs'] else ''))
    for base in metadata['navigation']['airports']:
        text(base['role'].upper()+': '+base['name']+' | '+
             ('Runways '+', '.join(base['runways']) if base['runways'] else 'Helipad / no runway'))
        text(' | '.join(base['radios']) or 'No catalogue ATC frequency',small)
    y+=12
    for point in metadata['navigation']['points']:
        draw.line((35,y,965,y),fill='#829394');y+=8
        text(point['role'].upper()+': '+point['label'])
        for label,key in (('DDM','ddm'),('DMS','dms'),('Decimal','decimal')):
            text(label+': '+point['coordinates'][key],small)
        y+=8
    y+=8;text(metadata['navigation']['note'],small,'#695746')
    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()
