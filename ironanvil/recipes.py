"""Portable settings and replay from a generated mission, without executing its Lua."""
from dataclasses import asdict, fields, replace
import json
from pathlib import Path
import zipfile

from .model import MissionOptions

MAX_RECIPE_BYTES=1024*1024


def options_from_data(data):
    if not isinstance(data,dict):
        raise ValueError('This file does not contain mission settings')
    values=data.get('options')
    if not isinstance(values,dict):
        raise ValueError('This file does not contain Iron Anvil mission settings')
    allowed={field.name for field in fields(MissionOptions)}
    unknown=set(values)-allowed
    if unknown:
        raise ValueError('This recipe uses unsupported settings: '+', '.join(sorted(unknown)))
    values=values.copy()
    if 'line_units' in values:
        if not isinstance(values['line_units'],(list,tuple)) or not all(isinstance(v,str) for v in values['line_units']):
            raise ValueError('Invalid fortified-line settings')
        values['line_units']=tuple(values['line_units'])
    # Never import another player's filesystem destination into this machine.
    values['output_dir']=None
    try:
        return MissionOptions(**values).validate()
    except (TypeError,KeyError,AttributeError) as error:
        raise ValueError('Invalid mission settings in this file') from error


def read_recipe(path):
    path=Path(path)
    if path.stat().st_size>32*1024*1024:
        raise ValueError('This file is too large to import as mission settings')
    try:
        if path.suffix.lower()=='.miz':
            with zipfile.ZipFile(path) as archive:
                info=archive.getinfo('ironanvil.json')
                if info.file_size>MAX_RECIPE_BYTES:
                    raise ValueError('Mission settings are unexpectedly large')
                raw=archive.read(info)
        else:
            raw=path.read_bytes()
            if len(raw)>MAX_RECIPE_BYTES:
                raise ValueError('Mission settings are unexpectedly large')
        return options_from_data(json.loads(raw))
    except (zipfile.BadZipFile,KeyError,json.JSONDecodeError,UnicodeError) as error:
        raise ValueError('Choose an Iron Anvil mission (.miz) or exported settings (.json)') from error


def write_recipe(options,path):
    from . import __version__
    options.validate()
    path=Path(path)
    values=asdict(replace(options,output_dir=None))
    path.write_text(json.dumps({'format':'ironanvil-recipe','version':1,'app_version':__version__,
                               'options':values},indent=2)+'\n',encoding='utf-8')
    return path
