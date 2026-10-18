"""Cockpit-friendly coordinates and catalogue radios for public planning points."""
from __future__ import annotations

import math


def coordinate_formats(latitude, longitude):
    """Round before splitting fields so 59.999... never becomes 60 minutes."""
    if not (math.isfinite(latitude) and math.isfinite(longitude)
            and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError('Coordinates must be finite latitude/longitude values')

    def axis(value, positive, negative, width, seconds=False):
        hemisphere=positive if value >= 0 else negative
        scale=36000 if seconds else 60000
        whole, remainder=divmod(round(abs(value)*scale),scale)
        if seconds:
            minutes, tenths=divmod(remainder,600)
            return f'{hemisphere}{whole:0{width}d} {minutes:02d}\' {tenths/10:04.1f}"'
        return f"{hemisphere}{whole:0{width}d} {remainder/1000:06.3f}'"

    return {
        'decimal': f'{latitude:.5f}, {longitude:.5f}',
        'ddm': axis(latitude,'N','S',2)+' '+axis(longitude,'E','W',3),
        'dms': axis(latitude,'N','S',2,True)+' '+axis(longitude,'E','W',3,True),
    }


def airport_card(airport, role):
    radio=getattr(airport,'atc_radio',None)
    radios=[]
    for attribute,band in (('vhf_high_hz','VHF AM'),('uhf_hz','UHF AM'),
                           ('vhf_low_hz','VHF FM'),('hf_hz','HF')):
        frequency=getattr(radio,attribute,None)
        if frequency:
            radios.append(f'{band} {frequency/1_000_000:.3f} MHz')
    return {'name':airport.name,'role':role,'radios':radios,
            'runways':[runway.name for runway in airport.runways]}


def navigation_card(planner, home, alternate):
    # Never derive this from hidden facility_sites or runtime target positions.
    points=[dict(label=point['label'],role=point['role'],
                 coordinates=coordinate_formats(point['lat'],point['lon']))
            for point in planner['points']]
    bases=[airport_card(home,'Home')]
    if alternate:bases.append(airport_card(alternate,'Alternate'))
    return {'points':points,'airports':bases,
            'note':'DDM = degrees and decimal minutes; DMS = degrees, minutes and seconds. '
                   'Convoy coordinates are starting positions; F10 updates the live location. '
                   'Runways are available directions, not an assigned runway. Verify catalogue radios in DCS.'}
