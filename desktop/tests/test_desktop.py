"""Native Qt + real WebEngine smoke/integration checks; no backend optimization."""
import json
import time
from dataclasses import replace
from threading import get_ident
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QDialog, QLineEdit, QDoubleSpinBox, QComboBox
from qrescate_desktop.window import MainWindow
from qrescate_desktop.models import *

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

def wait(app,check,seconds=20):
    end=time.monotonic()+seconds
    while not check() and time.monotonic()<end:
        app.processEvents();time.sleep(.015)
    assert check()

@pytest.fixture
def window(app):
    w=MainWindow();w.show();wait(app,lambda:w.map_ready)
    yield w
    w.dirty=False;w.controller.busy=False;w.close();app.processEvents()

def js(app,w,code):
    answer=[];w.map.page().runJavaScript(code,lambda v:answer.append(v));wait(app,lambda:len(answer)>0);return answer[0]

def test_initial_view_empty_and_map_live(app,window):
    w=window
    assert not w.calculate.isEnabled() and not w.experiment_start.isEnabled()
    assert w.qubits.isReadOnly() and w.seed.value()==42 and w.shots.value()==512
    assert w.results_subtitle.text().startswith('Sin resultados')
    assert js(app,w,'outline.getBounds().getSouth() < -12.3 && outline.getBounds().getNorth() > -10.8')
    assert js(app,w,"document.querySelector('.leaflet-control-attribution').textContent.includes('OpenStreetMap')")
    assert js(app,w,"typeof L.map === 'function'")

def test_qwebchannel_edit_sync_limits_and_zones(app,window):
    w=window
    js(app,w,"setMode('base');map.fire('click',{latlng:L.latLng(-11.25,-74.63)});true")
    wait(app,lambda:w.scenario.base is not None)
    assert '-11.250000' in w.base_coords.text()
    for i in range(4):w.map_event({'action':'place','kind':'destination','lat':-11.2-i*.1,'lng':-74.6})
    assert len(w.scenario.destinations)==3 and not w.add_dest.isEnabled() and w.qubits.text()=='9 qubits'
    d=w.scenario.destinations[1];w.map_event({'action':'move','id':d.id,'lat':-11.6,'lng':-74.5});assert d.lat==-11.6
    z=Zone(uid(),'Operación',-11.3,-74.5,3000,'operation');w.scenario.zones.append(z);w.refresh()
    w.map_event({'action':'radius','id':z.id,'radius_m':5000});assert z.radius_m==5000
    w.map_event({'action':'move','id':z.id,'lat':-11.8,'lng':-74.5});assert z.lat==-11.8
    w.selection=z.id;w.refresh();assert js(app,w,'objects.getLayers().length')>=7
    w.delete_selected_zone();assert not w.scenario.zones
    w.delete_destination(d.id);assert len(w.scenario.destinations)==2
    w.delete_base();assert w.scenario.base is None

def test_json_ui_save_load(app,window,tmp_path,monkeypatch):
    w=window;file=tmp_path/'scenario.json';w.scenario.base=Point('h','Base',-11.253,-74.638);w.changed()
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a: (str(file),'JSON (*.json)'))
    assert w.save_scenario();assert file.exists() and not w.dirty
    w.scenario=Scenario();w.dirty=False
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(file),'JSON (*.json)'))
    w.load_scenario();assert w.scenario.base.name=='Base'
    for i in range(5):w.navigate(i);assert w.pages.currentIndex()==i

class TestBackend:
    __test__=False
    def __init__(self):self.cancelled=False;self.calls=0;self.thread_ids=[];self.request=None
    def capabilities(self):return Capabilities(connected=True,experiments=True,cancellation=True)
    def submit(self,s):self.thread_ids.append(get_ident());self.request=s;return 'job-1'
    def status(self,id):
        self.calls+=1
        if self.cancelled:return JobSnapshot(id,'cancelled')
        if self.calls==1:return JobSnapshot(id,'running',messages=['Calculando sin porcentaje'])
        return JobSnapshot(id,'completed',results=[MethodResult('exact',cost=17,valid=True,gap_percent=0,duration_seconds=.1,visit_order=['h','a','h'],geometry=Geometry(coordinates=[[-74.638,-11.253],[-74.1,-11.1],[-74.638,-11.253]]),messages=['Resultado de servicio de prueba'])])
    def cancel(self,id):self.cancelled=True
    def submit_experiments(self,s,seeds):self.seeds=seeds;return self.submit(s)

def test_async_result_render_geometry_visibility_and_exports(app,tmp_path,monkeypatch):
    b=TestBackend();w=MainWindow(b);w.show();wait(app,lambda:w.caps.connected and w.map_ready)
    w.replace(Scenario(base=Point('h','Base',-11.253,-74.638),destinations=[Point('a','Destino',-11.1,-74.1)]))
    assert w.calculate.isEnabled()
    w.calculate_job();assert w.controller.busy
    wait(app,lambda:w.job_state=='completed')
    assert b.thread_ids[0]!=get_ident() and w.results[0].cost==17
    assert js(app,w,'routes.getLayers().filter(x=>x instanceof L.GeoJSON).length')==1
    w.route_checks['exact'].setChecked(False);app.processEvents();assert js(app,w,'routes.getLayers().length')==0
    for extension,kind in [('json','JSON (*.json)'),('csv','CSV (*.csv)')]:
        file=tmp_path/('results.'+extension);monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,file=file,kind=kind:(str(file),kind));w.export_history();assert file.exists()
    assert json.loads((tmp_path/'results.json').read_text(encoding='utf-8'))['history'][0]['snapshot']['results'][0]['cost']==17
    w.scenario.destinations[0].lat=-12;w.changed();assert not w.results
    assert b.request.destinations[0].lat==-11.1
    w.dirty=False;w.close()

def test_async_cancel_and_experiment_service(app):
    b=TestBackend();w=MainWindow(b);w.show();wait(app,lambda:w.caps.connected and w.map_ready)
    w.replace(Scenario(base=Point('h','Base',-11.253,-74.638),destinations=[Point('a','A',-11.1,-74.1)]))
    w.run_experiments();wait(app,lambda:bool(w.controller.job_id));assert b.seeds==[3,7,42]
    w.controller.cancel();wait(app,lambda:w.job_state=='cancelled');assert w.controller.history[-1]['kind']=='experiments'
    w.dirty=False;w.close()

def test_native_point_and_zone_editors(app,window):
    w=window;p=Point('h','Base',-11.253,-74.638);w.scenario.base=p
    def accept_point():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,QDialog)
        dialog.findChildren(QLineEdit)[0].setText('Base editada')
        dialog.findChildren(QDoubleSpinBox)[0].setValue(-11.5);dialog.accept()
    QTimer.singleShot(50,accept_point);w.edit_point(p)
    assert p.name=='Base editada' and p.lat==-11.5
    z=Zone('z','Zona',-11.3,-74.5,3000,'operation')
    def accept_zone():
        dialog=QApplication.activeModalWidget();dialog.findChildren(QLineEdit)[0].setText('Exclusión editada')
        dialog.findChild(QComboBox).setCurrentIndex(1)
        dialog.findChildren(QDoubleSpinBox)[2].setValue(8);dialog.accept()
    QTimer.singleShot(50,accept_zone);assert w.zone_editor(z)
    assert z.kind=='exclusion' and z.radius_m==8000 and z.name=='Exclusión editada'

def test_backend_error_is_reported_without_fake_results(app):
    class FaultBackend(TestBackend):
        def submit(self,s):raise ConnectionError('Servicio de prueba no disponible')
    w=MainWindow(FaultBackend());w.show();wait(app,lambda:w.caps.connected and w.map_ready)
    w.replace(Scenario(base=Point('h','Base',-11.253,-74.638),destinations=[Point('a','A',-11.1,-74.1)]))
    w.calculate_job();wait(app,lambda:w.job_state=='error')
    assert not w.results and not w.controller.busy
    assert 'Servicio de prueba no disponible' in w.result_message.text()
    assert w.controller.history[-1]['snapshot']['state']=='error'
    w.dirty=False;w.close()

def test_invalid_file_preserves_current_scenario(app,window,tmp_path,monkeypatch):
    file=tmp_path/'bad.json';file.write_text('{"schema_version":99}',encoding='utf-8')
    previous=window.scenario.to_dict();messages=[]
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(file),'JSON (*.json)'))
    monkeypatch.setattr(QMessageBox,'critical',lambda *a:messages.append(a[-1]))
    window.load_scenario();assert window.scenario.to_dict()==previous and messages

def test_theme_switches_widgets_and_map_without_resetting_scenario(app,window):
    w=window;w.scenario.base=Point('h','Base',-11.253,-74.638);w.changed();before=w.scenario.to_dict()
    w.theme_combo.setCurrentIndex(w.theme_combo.findData('dark'))
    assert w.theme=='dark' and '#121c2c' in w.styleSheet()
    assert js(app,w,"document.body.classList.contains('dark')")
    assert w.scenario.to_dict()==before
    w.theme_combo.setCurrentIndex(w.theme_combo.findData('light'))
    assert not js(app,w,"document.body.classList.contains('dark')")
    assert w.scenario.to_dict()==before

def test_viewport_zoom_pan_and_outside_edits_are_restricted(app,window):
    w=window
    assert js(app,w,'map.getMinZoom() > 0')
    js(app,w,'map.setZoom(1,{animate:false});true')
    assert js(app,w,'map.getZoom() >= map.getMinZoom()')
    js(app,w,'map.panTo([-12.046,-77.043],{animate:false});true')
    assert js(app,w,'inSatipo(map.getCenter().lat,map.getCenter().lng)')
    js(app,w,"setMode('base');map.fire('click',{latlng:L.latLng(-12.046,-77.043)});true")
    assert w.scenario.base is None
    w.map_event({'action':'place','kind':'base','lat':-11.253,'lng':-74.638})
    old=w.scenario.base.to_dict() if hasattr(w.scenario.base,'to_dict') else (w.scenario.base.lat,w.scenario.base.lng)
    w.map_event({'action':'move','id':w.scenario.base.id,'lat':0,'lng':0})
    assert (w.scenario.base.lat,w.scenario.base.lng)==old
    assert js(app,w,'mask.options.fillOpacity > .9')

def test_no_pasar_button_creates_an_editable_exclusion(app,window,monkeypatch):
    w=window
    def configure(z):z.name='Puente cerrado';z.radius_m=1200;return True
    monkeypatch.setattr(w,'zone_editor',configure)
    w.exclusion_button.click();app.processEvents()
    assert js(app,w,"mode==='exclusion'")
    js(app,w,"map.fire('click',{latlng:L.latLng(-11.3,-74.5)});true")
    wait(app,lambda:len(w.scenario.zones)==1)
    zone=w.scenario.zones[0];assert zone.kind=='exclusion' and zone.radius_m==1200
    assert 'Puente cerrado' in w.zones_combo.currentText()
    assert js(app,w,"objects.getLayers().some(x=>x instanceof L.Circle && x.options.color==='#e65c4b')")
    w.delete_selected_zone();assert not w.scenario.zones
