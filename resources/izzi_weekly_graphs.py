"""Native Izzi line charts; Python only assembles reviewed series and metadata."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

COLORS = ['#175b8c','#9b4318','#606a24','#4d405d','#8c416d','#525252','#007f78']
DASHES = ['', '8 4', '2 4', '8 3 2 3', '9 4', '2 3', '']


def series(name, index, points):
    return {'name': name, 'color': COLORS[index], 'dash': DASHES[index], 'points': points}


def point(x, y, tooltip):
    return {'x': x, 'y': y, 'tooltip': tooltip}


class IzziWeeklyGraphs:
    def __init__(self, izzi):
        self.temp = tempfile.TemporaryDirectory(prefix='alpha60-izzi-weekly-')
        self.directory = Path(self.temp.name)
        source = Path(__file__).with_name('izzi-weekly-graphs.cc')
        self.executable = self.directory/'weekly-graphs'
        subprocess.run(['g++','-std=c++20','-O2','-I'+str(izzi/'src'),str(source),'-o',str(self.executable)],check=True)
        self.provenance = {
            'library': 'Izzi',
            'commit': subprocess.check_output(['git','-C',str(izzi),'rev-parse','HEAD'],text=True).strip(),
            'line_graph_header_sha256': hashlib.sha256((izzi/'src/izzi-svg-graphs-line.h').read_bytes()).hexdigest(),
            'renderer_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'functions': ['svg::make_line_graph','svg::transform_to_graph_points','svg::make_marker_instance'],
        }
        self.specifications = {}

    def render(self, site, name, spec, inline=True):
        self.specifications[name] = spec
        source = self.directory/(name+'.json')
        source.write_text(json.dumps(spec,ensure_ascii=False))
        dest = site/'resources'/name
        subprocess.run([str(self.executable),str(source),str(dest)],check=True,stdout=subprocess.DEVNULL)
        path=site/'resources'/(name+'.svg')
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        tree=ET.parse(path);root=tree.getroot()
        root.set('id',name);root.set('role','group');root.set('class','analysis-svg')
        root.set('aria-label',spec.get('accessible_title',spec['title'])+'. '+spec['description'])
        for el in root:
            if el.tag.endswith('}title'):el.text=spec['title']
        ET.SubElement(root,'{http://www.w3.org/2000/svg}desc').text=spec['description']
        # Every chart can be safely embedded inline beside other charts.
        seen=set()
        for i,el in enumerate(root.iter()):
            if el is root:continue
            if el.get('id'):
                el.set('id',name+'-'+el.get('id')+'-'+str(i))
            if el.get('id'):assert el.get('id') not in seen;seen.add(el.get('id'))
        tree.write(path,encoding='unicode')
        if inline:shutil.copyfile(path,site/'_includes'/path.name)

    def save_ledger(self, path):
        path.write_text(json.dumps({'renderer':self.provenance,'charts':self.specifications},ensure_ascii=False,indent=2)+'\n')
