"""Public planning information, with deliberate separation from hidden objectives."""
from dcs import mapping


def search_intelligence(target, theatre, aircraft, rng):
    radius = 2500 if aircraft.helicopter else 4500
    bearing = rng.randrange(360)
    center = target
    for turn in (0,45,90,135,180,225,270,315):
        candidate = target.point_from_heading(bearing+turn, radius*.45)
        location = candidate.latlng()
        if theatre.contains(location.lat,location.lng):
            center=candidate;break
    location=center.latlng()
    return {'mode':'search','center':{'x':center.x,'z':center.y},'latitude':location.lat,'longitude':location.lng,
            'radius':radius,'required_seconds':45,'points':50,
            'description':'Stay airborne inside the search area for 45 continuous seconds, then request the shared reconnaissance check-in. This is a radio/intelligence game rule, not simulated sensor recognition.'}


def planner_metadata(terrain, home, target, alternate, operation, intelligence,ownership=None):
    def point(label, role, position):
        location=position.latlng()
        return {'label':label,'role':role,'lat':location.lat,'lon':location.lng,'x':position.x,'z':position.y}
    points=[point(home.name,'home',home.position)]
    if alternate:points.append(point(alternate.name,'alternate',alternate.position))
    if intelligence:
        search=mapping.Point(intelligence['center']['x'],intelligence['center']['z'],terrain)
        marker=point('Search area','search',search);marker['radius']=intelligence['radius'];points.append(marker)
    elif operation:
        for goal in operation['objectives']:
            points.append(point(goal['title'],'required' if goal['required'] else 'bonus',
                          mapping.Point(goal['position']['x'],goal['position']['z'],terrain)))
        if operation.get('response'):
            position=operation['response']['staging']
            points.append(point('Response staging','response',mapping.Point(position['x'],position['z'],terrain)))
        if operation.get('convoy'):
            position=operation['convoy']['destination']
            points.append(point('Supply delivery','delivery',mapping.Point(position['x'],position['z'],terrain)))
    else:points.append(point('Main target','required',target))
    return {'points':points,'intelligence':'search' if intelligence else 'precise',
            'airfield_sides':{str(key):value for key,value in (ownership or {}).items()},
            'note':'Planning schematic and approximate coastlines; check DCS terrain, obstacles, routes and loadouts.'}
