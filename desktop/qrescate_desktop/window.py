from __future__ import annotations
import csv
import io
import json
from dataclasses import asdict
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence, QPalette, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QStackedWidget, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QComboBox, QFileDialog, QMessageBox, QInputDialog,
    QDialog, QDialogButtonBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QProgressBar, QPlainTextEdit, QSizePolicy, QApplication, QLabel,
)
from .models import Scenario, Point, Zone, Capabilities, METHODS, STATES, uid, number, validate_for_run
from .backend import DisconnectedBackend
from .controller import Controller
from .map_widget import MapView
from .widgets import label, button, frame, icon, StatCard, ResultCard, STYLE, theme_style
from .geography import in_satipo, validate_coverage

def spin(value, low, high):
    w=QSpinBox();w.setRange(low,high);w.setValue(value);return w

def scroll(widget):
    s=QScrollArea();s.setWidgetResizable(True);s.setWidget(widget);return s

def table(headers):
    t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().hide();return t

class MainWindow(QMainWindow):
    def __init__(self, backend=None):
        super().__init__()
        palette=QPalette()
        for role,color in [(QPalette.ColorRole.Window,'#ffffff'),(QPalette.ColorRole.Base,'#ffffff'),(QPalette.ColorRole.Text,'#142344'),(QPalette.ColorRole.WindowText,'#142344'),(QPalette.ColorRole.Button,'#ffffff'),(QPalette.ColorRole.ButtonText,'#142344')]:palette.setColor(role,QColor(color))
        QApplication.instance().setPalette(palette)
        self.setPalette(palette)
        self.setWindowTitle('Q-Rescate · Planificación de recorridos · Satipo, Junín')
        self.setWindowIcon(icon('logo','#1477dc'));self.resize(1586,990);self.setMinimumSize(1360,850)
        self.setStyleSheet(STYLE)
        self.settings=QSettings('Q-Rescate','Desktop')
        self.theme=self.settings.value('appearance','light')
        self.scenario=Scenario();self.caps=Capabilities();self.dirty=False;self.path=None
        self.selection=None;self.results=[];self.result_scenario=None;self.loading=False;self.map_ready=False
        self.visibility={m:True for m in METHODS};self.job_state='ready'
        self.controller=Controller(backend or DisconnectedBackend(),self)
        self.controller.updated.connect(self.job_update);self.controller.capabilities_ready.connect(self.apply_caps)
        shell=QWidget();shell.setObjectName('shell');self.setCentralWidget(shell)
        root=QHBoxLayout(shell);root.setContentsMargins(0,0,10,0);root.setSpacing(14)
        self.sidebar=frame('sidebar');self.sidebar.setFixedWidth(216);nav=QVBoxLayout(self.sidebar);nav.setContentsMargins(9,14,9,18);nav.setSpacing(9)
        brand=QHBoxLayout();logo=label('');logo.setPixmap(icon('logo','#1579d9',31).pixmap(31,31));brand.addWidget(logo);brand.addWidget(label('Q-Rescate','brand'));brand.addStretch();nav.addLayout(brand);nav.addSpacing(17)
        self.nav_buttons=[]
        for i,(title,glyph) in enumerate([('Dashboard','home'),('Escenarios','map'),('Experimentos','flask'),('Resultados','chart')]):
            b=button(title,lambda checked=False,i=i:self.navigate(i),'nav',glyph);b.setCheckable(True);nav.addWidget(b);self.nav_buttons.append(b)
        nav.addStretch()
        nav.addWidget(label('Apariencia','muted'));self.theme_combo=QComboBox();self.theme_combo.addItem('☀  Modo claro','light');self.theme_combo.addItem('☾  Modo oscuro','dark');self.theme_combo.setCurrentIndex(max(0,self.theme_combo.findData(self.theme)));self.theme_combo.currentIndexChanged.connect(lambda:self.apply_theme(self.theme_combo.currentData()));nav.addWidget(self.theme_combo)
        self.offline=label('Backend no conectado','muted',True);nav.addWidget(self.offline)
        nav.addWidget(button('Ayuda',lambda:self.navigate(4),'nav','help'));root.addWidget(self.sidebar)
        self.pages=QStackedWidget();root.addWidget(self.pages,1)
        self.build_dashboard();self.build_scenarios();self.build_experiments();self.build_history();self.build_help()
        self.navigate(0);self.refresh();self.apply_theme(self.theme)
        self.statusBar().showMessage('Listo · Backend no conectado · Cobertura: provincia de Satipo, Junín')
        for title,keys,fn in [('Guardar escenario','Ctrl+S',self.save_scenario),('Abrir escenario','Ctrl+O',self.load_scenario),('Cancelar herramienta','Escape',lambda:self.set_mode(''))]:
            a=QAction(title,self);a.setShortcut(QKeySequence(keys));a.triggered.connect(fn);self.addAction(a)
        QTimer.singleShot(0,self.controller.connect_backend)

    def navigate(self,index):
        self.pages.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons):b.setChecked(i==index)
        if index==3:self.refresh_history()

    def apply_theme(self,theme):
        self.theme='dark' if theme=='dark' else 'light';dark=self.theme=='dark'
        self.theme_combo.blockSignals(True);self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.theme));self.theme_combo.blockSignals(False)
        self.settings.setValue('appearance',self.theme)
        palette=QPalette()
        for role,color in [(QPalette.ColorRole.Window,'#1c293e' if dark else '#ffffff'),(QPalette.ColorRole.Base,'#1c293e' if dark else '#ffffff'),(QPalette.ColorRole.Text,'#e4edf9' if dark else '#142344'),(QPalette.ColorRole.WindowText,'#e4edf9' if dark else '#142344'),(QPalette.ColorRole.Button,'#1c293e' if dark else '#ffffff'),(QPalette.ColorRole.ButtonText,'#e4edf9' if dark else '#142344')]:palette.setColor(role,QColor(color))
        QApplication.instance().setPalette(palette);self.setPalette(palette);self.setStyleSheet(theme_style(self.theme))
        for method,(_,color) in METHODS.items():
            tone={'exact':'#72b6ff','greedy':'#ffc363','qaoa':'#bd8aff'}[method] if dark else color
            self.route_checks[method].setStyleSheet(f'color:{tone};font-size:11px;')
            self.result_cards[method].findChild(QLabel,'methodTitle').setStyleSheet(f'color:{tone};')
        self.result_message.setStyleSheet('background:#4a3c25;color:#f4d890;padding:7px;border:1px solid #725a2b;border-radius:4px;' if dark else 'background:#fff1c8;color:#725821;padding:7px;border:1px solid #f3e1a7;border-radius:4px;')
        self.refresh()
        if self.map_ready:self.map.bridge.theme.emit(self.theme)

    def build_dashboard(self):
        page=QWidget();row=QHBoxLayout(page);row.setContentsMargins(0,12,0,10);row.setSpacing(14)
        center=QWidget();col=QVBoxLayout(center);col.setContentsMargins(0,0,0,0);col.setSpacing(13)
        header=QHBoxLayout();badge=label('PLANIFICACIÓN LOCAL','badge');badge.setFixedWidth(200);header.addWidget(badge,0,Qt.AlignmentFlag.AlignTop)
        title=QVBoxLayout();title.setSpacing(1);title.addWidget(label('Planificación de recorridos','heading'));title.addWidget(label('Define tu zona y compara recorridos de emergencia','subtitle'));header.addLayout(title,1);col.addLayout(header)
        stats=QHBoxLayout();stats.setSpacing(12);self.stats=[]
        for text,glyph,color in [('Ambulancias','ambulance','#1684e7'),('Destinos','pin','#13b77c'),('Zonas excluidas','ban','#d7433c'),('Escenario','file','#8f69de')]:
            card=StatCard(text,glyph,color);card.setMinimumHeight(69);stats.addWidget(card,1);self.stats.append(card.value)
        self.stats[3].setStyleSheet('font-size:15px;font-weight:700;');col.addLayout(stats)
        mf=frame('mapFrame');grid=QGridLayout(mf);grid.setContentsMargins(1,1,1,1)
        self.map=MapView();self.map.bridge.received.connect(self.map_event);grid.addWidget(self.map,0,0)
        self.map.loadFinished.connect(lambda ok:self.map_load(ok))
        overlay=QWidget();overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);tools=QHBoxLayout(overlay);tools.setContentsMargins(8,8,8,0);tools.setSpacing(5)
        tools.addWidget(label('Satipo, Junín · provincia','badge'));tools.addStretch()
        for title,mode,glyph,color in [('Base','base','ambulance','#d84342'),('Zona de operación','operation','circle','#239c99'),('Excluir zona','exclusion','ban','#df534a'),('Agregar destino','destination','pin','#1673e6')]:
            b=button(title,lambda checked=False,m=mode:self.set_mode(m),'tool',glyph,color);b.setToolTip('Selecciona la herramienta y haz clic en el mapa');tools.addWidget(b)
        grid.addWidget(overlay,0,0,Qt.AlignmentFlag.AlignTop)
        self.legend=frame('card');leg=QVBoxLayout(self.legend);leg.setContentsMargins(10,7,10,7);leg.setSpacing(5)
        self.route_checks={}
        for m,(name,color) in METHODS.items():
            c=QCheckBox(name);c.setObjectName(m);c.setChecked(True);c.setStyleSheet(f'color:{color};font-size:11px;');c.toggled.connect(lambda on,m=m:self.toggle_route(m,on));leg.addWidget(c);self.route_checks[m]=c
        for text,glyph,color in [('Zona de operación','circle','#239c99'),('Exclusión','ban','#df534a')]:
            line=QHBoxLayout();im=label('');im.setPixmap(icon(glyph,color,17).pixmap(17,17));line.addWidget(im);line.addWidget(label(text,'muted'));leg.addLayout(line)
        grid.addWidget(self.legend,0,0,Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeft)
        self.legend.setContentsMargins(0,0,0,0)
        mf.setMinimumHeight(305);col.addWidget(mf,1)
        self.results_panel=frame('results');r=QVBoxLayout(self.results_panel);r.setContentsMargins(13,10,13,10);r.setSpacing(8)
        rr=QHBoxLayout();rr.addWidget(label('Comparación de resultados','section'));rr.addStretch();self.export_button=button('Exportar resultados',self.export_history,glyph='download');rr.addWidget(self.export_button);r.addLayout(rr)
        self.results_subtitle=label('Sin resultados · Un recorrido con regreso a la base','muted');r.addWidget(self.results_subtitle)
        cards=QHBoxLayout();cards.setSpacing(12);self.result_cards={}
        for m,(name,color) in METHODS.items():
            card=ResultCard(name,color);cards.addWidget(card,1);self.result_cards[m]=card
        r.addLayout(cards)
        self.result_message=label('Backend no conectado. Conecta un servicio para calcular y comparar recorridos.','muted',True)
        self.result_message.setStyleSheet('background:#fff1c8;color:#725821;padding:7px;border:1px solid #f3e1a7;border-radius:4px;');r.addWidget(self.result_message)
        col.addWidget(self.results_panel);row.addWidget(center,1)
        self.panel=frame('panel');self.panel.setFixedWidth(344);pl=QVBoxLayout(self.panel);pl.setContentsMargins(15,14,15,12);pl.setSpacing(9)
        pl.addWidget(label('Configurar escenario','section'))
        content=QWidget();content.setObjectName('panelContent');p=QVBoxLayout(content);p.setContentsMargins(0,0,0,0);p.setSpacing(8)
        p.addWidget(label('Escenario'));self.name=QLineEdit(self.scenario.name);self.name.setMaxLength(150);self.name.editingFinished.connect(self.config_changed);p.addWidget(self.name)
        p.addSpacing(5);p.addWidget(label('Punto de partida'))
        base_row=QHBoxLayout();self.base_button=button('H  · Colocar base',lambda:self.base_action());base_row.addWidget(self.base_button,1);self.base_delete=button('×',self.delete_base,'tiny');self.base_delete.setToolTip('Eliminar base');base_row.addWidget(self.base_delete);p.addLayout(base_row)
        self.base_coords=label('Selecciona una ubicación en el mapa','muted');p.addWidget(self.base_coords)
        p.addWidget(label('Destinos'));self.dest_host=QWidget();self.dest_layout=QVBoxLayout(self.dest_host);self.dest_layout.setContentsMargins(0,0,0,0);self.dest_layout.setSpacing(6);p.addWidget(self.dest_host)
        self.add_dest=button('＋  Agregar destino',lambda:self.set_mode('destination'));p.addWidget(self.add_dest)
        p.addSpacing(3);p.addWidget(label('Zonas de operación y exclusión'))
        self.exclusion_button=button('⊘  Marcar zona de NO PASAR',lambda:self.set_mode('exclusion'),glyph='ban',color='#df534a');self.exclusion_button.setToolTip('Haz clic dentro de Satipo para ubicar el centro; luego define el radio y el motivo del bloqueo.');p.addWidget(self.exclusion_button)
        self.zones_combo=QComboBox();self.zones_combo.currentIndexChanged.connect(self.select_zone);p.addWidget(self.zones_combo)
        zr=QHBoxLayout();self.zone_edit=button('Editar zona',self.edit_selected_zone);self.zone_delete=button('Eliminar',self.delete_selected_zone);zr.addWidget(self.zone_edit);zr.addWidget(self.zone_delete);p.addLayout(zr)
        p.addWidget(label('Comparar métodos'));mr=QGridLayout();self.methods={}
        for m,title in [('exact','Clásico exacto'),('qaoa','QAOA'),('greedy','Greedy')]:
            c=QCheckBox(title);c.setObjectName(m);c.setChecked(m in self.scenario.config.methods);c.toggled.connect(self.config_changed);mr.addWidget(c,1 if m=='greedy' else 0,1 if m=='qaoa' else 0);self.methods[m]=c
        p.addLayout(mr)
        advanced=QGroupBox('Parámetros QAOA');al=QVBoxLayout(advanced);fields=QHBoxLayout()
        self.seed=spin(42,0,2147483647);self.shots=spin(512,1,8192);self.qubits=QLineEdit('0 qubits');self.qubits.setReadOnly(True);self.qubits.setToolTip('Información: n² para la codificación por posición; no es un parámetro libre.')
        for text,w in [('Semilla',self.seed),('Qubits',self.qubits),('Shots',self.shots)]:
            w.setMinimumWidth(0);w.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
            c=QVBoxLayout();c.addWidget(label(text,'muted'));c.addWidget(w);fields.addLayout(c,1)
        al.addLayout(fields);extra=QWidget();more=QHBoxLayout(extra);more.setContentsMargins(0,0,0,0);self.reps=spin(1,1,10);self.maxiter=spin(35,1,1000)
        for text,w in [('Repeticiones',self.reps),('Iteraciones máx.',self.maxiter)]:
            c=QVBoxLayout();c.addWidget(label(text,'muted'));c.addWidget(w);more.addLayout(c)
        extra.hide();toggle=button('Más opciones  ▾',lambda:extra.setVisible(not extra.isVisible()),'tiny');al.addWidget(toggle);al.addWidget(extra);p.addWidget(advanced)
        for w in (self.seed,self.shots,self.reps,self.maxiter):w.valueChanged.connect(self.config_changed)
        self.timeout=spin(300,1,900);self.timeout.setSuffix(' s');more.addWidget(label('Plazo'));more.addWidget(self.timeout);self.timeout.valueChanged.connect(self.config_changed)
        self.limit_label=label('1 base · 1 vehículo · hasta 3 destinos QAOA','muted',True);p.addWidget(self.limit_label)
        self.calculate=button('Calcular recorridos',self.calculate_job,'primary');p.addWidget(self.calculate)
        self.cancel_button=button('Cancelar cálculo',self.controller.cancel);self.cancel_button.hide();p.addWidget(self.cancel_button)
        self.progress=QProgressBar();self.progress.hide();p.addWidget(self.progress)
        p.addWidget(button('Cargar ejemplo · demostración',self.load_example));p.addWidget(label('Una unidad visita cada destino y regresa a la base. QAOA se ejecutará en simulador.','muted',True));p.addStretch()
        pl.addWidget(scroll(content),1);self.state_label=label('Listo · Backend no conectado','muted',True);pl.addWidget(self.state_label)
        row.addWidget(self.panel);self.pages.addWidget(page)

    def base_action(self):
        if self.scenario.base:self.edit_point(self.scenario.base)
        else:self.set_mode('base')

    def page_layout(self,title,subtitle):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(12,20,18,18);layout.setSpacing(15)
        layout.addWidget(label(title,'heading'));layout.addWidget(label(subtitle,'subtitle',True));self.pages.addWidget(page);return layout

    def build_scenarios(self):
        p=self.page_layout('Escenarios','Guarda y recupera la base, los destinos, las zonas y los parámetros en JSON.')
        row=QHBoxLayout();row.addWidget(button('Nuevo escenario',self.new_scenario));row.addWidget(button('Abrir JSON…',self.load_scenario));row.addWidget(button('Guardar JSON…',self.save_scenario));row.addStretch();p.addLayout(row)
        self.scenario_summary=label('','subtitle',True);p.addWidget(self.scenario_summary)
        self.json_preview=QPlainTextEdit();self.json_preview.setReadOnly(True);p.addWidget(self.json_preview,1)
        p.addWidget(label('Cobertura restringida a la provincia de Satipo, Junín. El contorno provincial es referencial (fuente: INEI, servicio Osinergmin).','muted',True))
        p.addWidget(button('Volver al mapa de la provincia',lambda:(self.navigate(0),self.map.command('province'))))

    def build_experiments(self):
        p=self.page_layout('Experimentos','Repite el escenario actual con varias semillas. El backend proporciona los estados y las métricas.')
        f=frame();form=QFormLayout(f);self.seeds=QLineEdit('3, 7, 42');form.addRow('Semillas (separadas por comas)',self.seeds)
        self.experiment_start=button('Ejecutar experimentos',self.run_experiments,'primary');form.addRow(self.experiment_start);p.addWidget(f)
        self.experiment_note=label('Backend no conectado. El servicio de experimentos todavía no está disponible.','muted',True);p.addWidget(self.experiment_note)
        self.experiment_table=table(['Semilla','Método','Estado','Costo','Gap (%)','Validez','Duración (s)','Mensaje']);p.addWidget(self.experiment_table,1)
        p.addWidget(button('Exportar historial de experimentos',self.export_history))

    def build_history(self):
        p=self.page_layout('Historial de resultados','Resultados recibidos durante esta sesión. Cada registro conserva el escenario enviado al backend.')
        row=QHBoxLayout();row.addWidget(button('Exportar JSON / CSV…',self.export_history,glyph='download'));row.addStretch();p.addLayout(row)
        self.history_table=table(['Fecha UTC','Escenario','Estado','Método','Costo','Gap (%)','Validez','Duración (s)']);self.history_table.itemSelectionChanged.connect(self.history_selection);p.addWidget(self.history_table,1)
        self.history_detail=QPlainTextEdit('Sin resultados');self.history_detail.setReadOnly(True);self.history_detail.setMaximumHeight(235);p.addWidget(self.history_detail)

    def build_help(self):
        p=self.page_layout('Ayuda','Q-Rescate · Planificación de recorridos en Satipo, Junín')
        text=(
            'MAPA Y ESCENARIOS\n\nUsa la rueda o +/− para acercarte. Arrastra el fondo para desplazarte. Las teselas de OpenStreetMap requieren Internet. '
            'El contorno turquesa delimita Satipo, Junín; el exterior queda sombreado. No puedes alejarte más allá de la vista provincial ni desplazarte fuera de su cobertura. '
            'Solo se aceptan bases, destinos y centros de zonas dentro de Satipo. El límite cartográfico es referencial (INEI, servicio Osinergmin).\n\n'
            'Pulsa Base o Agregar destino y haz clic en el mapa. Arrastra los marcadores para moverlos. Pulsa un destino en el panel para renombrarlo o editar sus coordenadas; × lo elimina. '
            'Un clic derecho sobre un objeto abre su editor.\n\n'
            'Para crear una zona, selecciona Zona de operación o Excluir zona y haz clic para ubicar su centro. Edita nombre, tipo, centro y radio en el formulario. '
            'El botón «Marcar zona de NO PASAR» crea un círculo rojo de exclusión; su nombre puede indicar el motivo, como puente cerrado o vía inundada. '
            'Selecciona un círculo para mostrar sus controles: arrastra el centro para moverlo o el control del borde para cambiar el radio. Escape cancela la herramienta activa.\n\n'
            'Guarda y abre escenarios en Escenarios (Ctrl+S / Ctrl+O). Cargar ejemplo crea únicamente puntos y zonas de demostración, sin resultados.\n\n'
            'MODELO Y MÉTRICAS\n\nUna unidad sale de la base, visita cada destino exactamente una vez y regresa. La primera integración admite hasta tres destinos QAOA; los límites los declara el backend. '
            'Qubits: n² para n destinos con codificación por posición; no se eligen libremente. QAOA utiliza simulación Qiskit, no hardware físico. '
            'Exacto y greedy se comparan con QAOA sobre la misma matriz dirigida de costos.\n\n'
            'Semilla: controla la aleatoriedad; 42 es el valor inicial. Shots: cantidad de muestras configuradas; inicialmente 512. Repeticiones e iteraciones son parámetros del optimizador. '
            'Las semillas no garantizan igualdad entre distintas versiones o equipos.\n\n'
            'Costo: objetivo original y unidad informada por el motor. Gap: 100 × (costo − óptimo exacto) / |óptimo exacto|; puede no estar disponible cuando la referencia es cero. '
            'Validez: comprobación de restricciones. Duración: tiempo reportado por el backend, no tiempo de QPU. Un gap cero no demuestra ventaja cuántica.\n\n'
            'BACKEND\n\nSin conexión puedes editar y guardar escenarios. Calcular y ejecutar experimentos se habilitan cuando las capacidades lo permiten. '
            'Los estados son Listo, Calculando, Completado, Cancelado y Error. Cancelar solicita la cancelación; el motor confirma el estado final. '
            'No se muestra un porcentaje inventado.\n\n'
            'APARIENCIA\n\nSelecciona Modo claro o Modo oscuro en el menú lateral. La elección se conserva al volver a abrir la aplicación y se aplica también al mapa.\n\n'
            'El backend se encarga de la red vial, cierres, Dijkstra, matriz dirigida, QUBO y algoritmos. Visualizar OpenStreetMap no significa que OSMnx o el ruteo vial estén conectados. '
            'Las rutas solo se dibujan cuando se reciben geometrías del motor. Los resultados históricos sintéticos no se convierten en rutas reales. '
            'Grover es un experimento complementario separado y no forma parte del TSP principal de esta interfaz.'
        )
        body=label(text,'',True);body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);p.addWidget(scroll(body),1)

    def config_changed(self,*args):
        if self.loading:return
        if self.controller.busy:return
        previous=self.scenario.dumps()
        self.scenario.name=self.name.text().strip() or 'Nuevo escenario'
        c=self.scenario.config;c.methods=[m for m,w in self.methods.items() if w.isChecked()]
        c.seed=self.seed.value();c.shots=self.shots.value();c.reps=self.reps.value();c.maxiter=self.maxiter.value()
        c.timeout_seconds=self.timeout.value()
        if previous!=self.scenario.dumps():self.changed()

    def changed(self):
        self.dirty=True
        # A result belongs to its immutable submitted snapshot, never to edited points.
        self.results=[];self.result_scenario=None
        self.refresh()

    def apply_caps(self,caps):
        self.caps=caps
        self.loading=True
        self.shots.setRange(caps.shots_min,caps.shots_max);self.reps.setMaximum(caps.reps_max);self.maxiter.setMaximum(caps.maxiter_max)
        if caps.fixed_reps is not None:self.reps.setValue(caps.fixed_reps);self.scenario.config.reps=caps.fixed_reps
        if caps.fixed_maxiter is not None:self.maxiter.setValue(caps.fixed_maxiter);self.scenario.config.maxiter=caps.fixed_maxiter
        self.scenario.config.shots=self.shots.value();self.scenario.config.reps=self.reps.value();self.scenario.config.maxiter=self.maxiter.value()
        self.loading=False;self.refresh()

    def refresh(self):
        self.loading=True
        s=self.scenario;c=s.config
        self.name.setText(s.name)
        self.name.setEnabled(not self.controller.busy)
        for m,w in self.methods.items():w.setChecked(m in c.methods);w.setEnabled(m in self.caps.methods and not self.controller.busy)
        for w,v in [(self.seed,c.seed),(self.shots,c.shots),(self.reps,c.reps),(self.maxiter,c.maxiter)]:w.setValue(v)
        for w in (self.seed,self.shots,self.reps,self.maxiter):w.setEnabled(not self.controller.busy)
        self.timeout.setValue(c.timeout_seconds);self.timeout.setMaximum(self.caps.timeout_max_seconds);self.timeout.setEnabled(not self.controller.busy)
        self.reps.setEnabled(not self.controller.busy and self.caps.fixed_reps is None);self.maxiter.setEnabled(not self.controller.busy and self.caps.fixed_maxiter is None)
        self.reps.setToolTip('Fijo en el motor: 1' if self.caps.fixed_reps is not None else 'Repeticiones QAOA')
        self.maxiter.setToolTip('Fijo en el motor: 35' if self.caps.fixed_maxiter is not None else 'Máximo de iteraciones')
        n=len(s.destinations);q=f'{n*n} qubits' if self.caps.qubit_encoding=='position_n_squared' else 'Según motor'
        self.qubits.setText(q)
        for w,v in zip(self.stats,[str(c.vehicles),str(n),str(sum(z.kind=='exclusion' for z in s.zones)),s.name]):w.setText(v);w.setToolTip(v)
        self.base_button.setText('H  · '+s.base.name if s.base else 'H  · Colocar base')
        self.base_button.setStyleSheet('text-align:left;'+(('color:#ff929b;' if self.theme=='dark' else 'color:#b52c37;') if s.base else ''))
        self.base_delete.setEnabled(bool(s.base) and not self.controller.busy)
        self.base_coords.setText(f'{s.base.lat:.6f}, {s.base.lng:.6f}' if s.base else 'Selecciona una ubicación en el mapa')
        self.clear_layout(self.dest_layout)
        if not n:self.dest_layout.addWidget(label('Sin destinos · agrega un punto en el mapa','muted',True))
        for i,d in enumerate(s.destinations):
            row=QHBoxLayout();b=button(f'{chr(65+i)}  · {d.name}',lambda checked=False,d=d:self.edit_point(d));b.setEnabled(not self.controller.busy);b.setStyleSheet('text-align:left;color:'+('#5ae0a6;' if self.theme=='dark' else '#12895a;'));b.setToolTip(f'{d.lat:.6f}, {d.lng:.6f} · Editar nombre o coordenadas');row.addWidget(b,1)
            x=button('×',lambda checked=False,id=d.id:self.delete_destination(id),'tiny');x.setEnabled(not self.controller.busy);x.setToolTip('Eliminar destino');row.addWidget(x);self.dest_layout.addLayout(row)
        self.add_dest.setEnabled(n<self.caps.max_destinations and not self.controller.busy)
        self.add_dest.setToolTip(f'Límite actual: {self.caps.max_destinations} destinos')
        self.zones_combo.clear();self.zones_combo.addItem('Sin zonas' if not s.zones else 'Selecciona una zona',None)
        for z in s.zones:self.zones_combo.addItem(f'{"◌" if z.kind=="operation" else "⊘"} {z.name} · {z.radius_m/1000:g} km',z.id)
        idx=self.zones_combo.findData(self.selection);self.zones_combo.setCurrentIndex(max(0,idx))
        self.zone_edit.setEnabled(idx>0 and not self.controller.busy);self.zone_delete.setEnabled(idx>0 and not self.controller.busy)
        self.offline.setText('Backend conectado' if self.caps.connected else 'Backend no conectado')
        self.limit_label.setText(f'{self.caps.max_bases} base · {self.caps.max_vehicles} vehículo · {self.caps.min_destinations}–{self.caps.max_qaoa_destinations} destinos QAOA\nMáximo: {self.caps.max_qubits} qubits · {self.caps.max_operation_zones} zona de operación')
        reason=validate_for_run(s,self.caps)
        self.calculate.setEnabled(not reason and not self.controller.busy);self.calculate.setToolTip(reason or 'Enviar escenario al backend')
        self.experiment_start.setEnabled(not reason and self.caps.experiments and not self.controller.busy)
        self.experiment_start.setToolTip(reason or ('' if self.caps.experiments else 'El backend no ofrece experimentos'))
        self.experiment_note.setText(reason or ('Servicio de experimentos disponible.' if self.caps.experiments else 'Experimentos no implementados en el adaptador local. Usa cálculos individuales con semilla, plazo y cancelación.'))
        self.cancel_button.setVisible(self.controller.busy);self.cancel_button.setEnabled(bool(self.controller.job_id) and self.caps.cancellation)
        self.cancel_button.setToolTip('Solicitar cancelación al backend' if self.caps.cancellation else 'El backend no ofrece cancelación')
        self.state_label.setText(STATES[self.job_state]+' · '+self.offline.text())
        self.scenario_summary.setText(f'{s.name} · {n} destinos · {len(s.zones)} zonas'+(' · Cambios sin guardar' if self.dirty else ''))
        self.json_preview.setPlainText(s.dumps())
        self.export_button.setEnabled(bool(self.controller.history))
        self.loading=False
        self.render_map();self.render_results()

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
            if item.layout():MainWindow.clear_layout(item.layout())

    def map_load(self,ok):
        if not ok:self.statusBar().showMessage('Error al cargar el mapa local. Revisa los archivos de assets.')

    def render_map(self):
        if self.map_ready:
            self.map.bridge.theme.emit(self.theme)
            self.map.bridge.locked.emit(self.controller.busy)
            self.map.bridge.scene.emit(self.scenario.dumps())
            self.map.bridge.selection.emit(self.selection or '')

    def set_mode(self,mode):
        if self.controller.busy:
            self.statusBar().showMessage('Espera a que termine el cálculo para editar el escenario.');return
        if mode=='destination' and len(self.scenario.destinations)>=self.caps.max_destinations:
            self.statusBar().showMessage(f'Límite: {self.caps.max_destinations} destinos.');return
        self.map.bridge.mode.emit(mode)
        names={'base':'colocar o mover la base','destination':'agregar un destino','operation':'dibujar una zona de operación','exclusion':'dibujar una zona de exclusión'}
        self.statusBar().showMessage('Haz clic en el mapa para '+names[mode]+'. Escape cancela.' if mode else 'Listo · Herramienta cancelada')

    def map_event(self,event):
        action=event.get('action')
        if action=='ready':self.map_ready=True;self.render_map();self.render_results();return
        if action=='coordinate':self.statusBar().showMessage(f'Ubicación: {event.get("lat",0):.6f}, {event.get("lng",0):.6f} · Satipo, Junín');return
        if self.controller.busy:return
        try:
            if action=='place':
                lat=number(event['lat'],-90,90);lng=number(event['lng'],-180,180);kind=event['kind']
                if not in_satipo(lat,lng):raise ValueError('Ubicación fuera de Satipo, Junín')
                if kind=='base':self.scenario.base=Point(self.scenario.base.id if self.scenario.base else uid(),'Base' if not self.scenario.base else self.scenario.base.name,lat,lng)
                elif kind=='destination':
                    if len(self.scenario.destinations)>=self.caps.max_destinations:return
                    self.scenario.destinations.append(Point(uid(),f'Punto de atención {len(self.scenario.destinations)+1}',lat,lng))
                elif kind in ('operation','exclusion'):
                    if kind=='operation' and sum(z.kind=='operation' for z in self.scenario.zones)>=self.caps.max_operation_zones:
                        raise ValueError('Solo se admite una zona de operación. Edita o elimina la existente.')
                    z=Zone(uid(),'Zona de operación' if kind=='operation' else 'Zona de exclusión',lat,lng,3000,kind)
                    if not self.zone_editor(z):return
                    self.scenario.zones.append(z);self.selection=z.id
                else:return
                self.changed();self.statusBar().showMessage('Escenario actualizado · Coordenadas sincronizadas')
            elif action in ('select','edit'):
                obj=self.find(event.get('id'));self.selection=obj.id if obj else None
                if action=='edit' and obj:
                    self.edit_zone(obj) if isinstance(obj,Zone) else self.edit_point(obj)
                self.refresh()
            elif action in ('move','radius'):
                obj=self.find(event.get('id'))
                if obj is None:return
                if action=='move':
                    lat=number(event['lat'],-90,90);lng=number(event['lng'],-180,180)
                    if not in_satipo(lat,lng):raise ValueError('Ubicación fuera de Satipo, Junín')
                    obj.lat=lat;obj.lng=lng
                elif isinstance(obj,Zone):obj.radius_m=number(event['radius_m'],10,500000)
                self.changed()
        except (ValueError,TypeError,KeyError) as exc:
            self.statusBar().showMessage('Cambio rechazado: '+str(exc));self.render_map()

    def find(self,id):
        return next((p for p in ([self.scenario.base] if self.scenario.base else [])+self.scenario.destinations+self.scenario.zones if p.id==id),None)

    def edit_point(self,point):
        if self.controller.busy:return
        d=QDialog(self);d.setWindowTitle('Editar ubicación');form=QFormLayout(d)
        name=QLineEdit(point.name);name.setMaxLength(150);lat=QDoubleSpinBox();lat.setRange(-90,90);lat.setDecimals(6);lat.setValue(point.lat)
        lng=QDoubleSpinBox();lng.setRange(-180,180);lng.setDecimals(6);lng.setValue(point.lng)
        form.addRow('Nombre',name);form.addRow('Latitud',lat);form.addRow('Longitud',lng)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject)
        if d.exec()==QDialog.DialogCode.Accepted:
            if not name.text().strip():QMessageBox.warning(self,'Nombre requerido','Escribe un nombre para la ubicación.');return
            if not in_satipo(lat.value(),lng.value()):QMessageBox.warning(self,'Fuera de cobertura','La ubicación debe estar dentro de Satipo, Junín.');return
            point.name=name.text().strip();point.lat=lat.value();point.lng=lng.value();self.changed()

    def zone_editor(self,z):
        d=QDialog(self);d.setWindowTitle('Configurar zona');f=QFormLayout(d);name=QLineEdit(z.name);name.setMaxLength(150)
        kind=QComboBox();kind.addItem('Operación','operation');kind.addItem('Exclusión','exclusion');kind.setCurrentIndex(kind.findData(z.kind))
        lat=QDoubleSpinBox();lat.setRange(-90,90);lat.setDecimals(6);lat.setValue(z.lat)
        lng=QDoubleSpinBox();lng.setRange(-180,180);lng.setDecimals(6);lng.setValue(z.lng)
        radius=QDoubleSpinBox();radius.setRange(.01,500);radius.setDecimals(3);radius.setValue(z.radius_m/1000);radius.setSuffix(' km')
        for title,w in [('Nombre',name),('Tipo',kind),('Latitud',lat),('Longitud',lng),('Radio',radius)]:f.addRow(title,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);f.addRow(b);b.accepted.connect(d.accept);b.rejected.connect(d.reject)
        if d.exec()!=QDialog.DialogCode.Accepted:return False
        if not name.text().strip():QMessageBox.warning(self,'Nombre requerido','Escribe un nombre para la zona.');return False
        if not in_satipo(lat.value(),lng.value()):QMessageBox.warning(self,'Fuera de cobertura','El centro de la zona debe estar dentro de Satipo, Junín.');return False
        if kind.currentData()=='operation' and any(other.kind=='operation' and other.id!=z.id for other in self.scenario.zones):
            QMessageBox.warning(self,'Zona de operación','Solo se admite una zona de operación.');return False
        z.name=name.text().strip();z.kind=kind.currentData();z.lat=lat.value();z.lng=lng.value();z.radius_m=radius.value()*1000
        return True

    def edit_zone(self,z):
        if not self.controller.busy and self.zone_editor(z):self.changed()

    def select_zone(self,*args):
        if not self.loading:
            self.selection=self.zones_combo.currentData();self.map.bridge.selection.emit(self.selection or '')
            self.zone_edit.setEnabled(bool(self.selection) and not self.controller.busy);self.zone_delete.setEnabled(bool(self.selection) and not self.controller.busy)

    def edit_selected_zone(self):
        z=self.find(self.zones_combo.currentData())
        if isinstance(z,Zone):self.edit_zone(z)
        else:self.statusBar().showMessage('Selecciona una zona para editarla.')

    def delete_selected_zone(self):
        if self.controller.busy:return
        id=self.zones_combo.currentData()
        if id:self.scenario.zones=[z for z in self.scenario.zones if z.id!=id];self.selection=None;self.changed()

    def delete_base(self):
        if not self.controller.busy:self.scenario.base=None;self.changed()

    def delete_destination(self,id):
        if not self.controller.busy:self.scenario.destinations=[p for p in self.scenario.destinations if p.id!=id];self.changed()

    def allow_replace(self):
        if self.controller.busy:
            QMessageBox.information(self,'Cálculo activo','Espera a que termine o solicita cancelación.');return False
        if self.dirty:
            answer=QMessageBox.question(self,'Cambios sin guardar','¿Guardar el escenario antes de continuar?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
            if answer==QMessageBox.StandardButton.Cancel:return False
            if answer==QMessageBox.StandardButton.Save:return self.save_scenario()
        return True

    def replace(self,s,path=None):
        validate_coverage(s)
        if self.caps.fixed_reps is not None and s.config.reps!=self.caps.fixed_reps:raise ValueError('El motor fija reps=1; este escenario contiene otro valor.')
        if self.caps.fixed_maxiter is not None and s.config.maxiter!=self.caps.fixed_maxiter:raise ValueError('El motor fija maxiter=35; este escenario contiene otro valor.')
        self.scenario=s;self.path=path;self.selection=None;self.results=[];self.result_scenario=None;self.job_state='ready';self.dirty=False;self.refresh()
        self.map.command('province')

    def new_scenario(self):
        if self.allow_replace():self.replace(Scenario())

    def load_example(self):
        if not self.allow_replace():return
        from .local_backend import from_example
        s=from_example()
        self.replace(s);self.dirty=True;self.refresh();self.statusBar().showMessage('Ejemplo del motor: ubicaciones ilustrativas. Calcular usará OSM en modo normal. Sin resultados precalculados.');self.navigate(0)

    def save_scenario(self):
        self.config_changed()
        path,_=QFileDialog.getSaveFileName(self,'Guardar escenario',str(self.path or Path.home()/'escenario-satipo.json'),'Escenario JSON (*.json)')
        if not path:return False
        try:
            Path(path).write_text(self.scenario.dumps(),encoding='utf-8');self.path=Path(path);self.dirty=False;self.refresh();self.statusBar().showMessage('Escenario guardado: '+path);return True
        except OSError as exc:QMessageBox.critical(self,'Error al guardar',str(exc));return False

    def load_scenario(self):
        if not self.allow_replace():return
        path,_=QFileDialog.getOpenFileName(self,'Abrir escenario','','Escenario JSON (*.json)')
        if not path:return
        try:
            if Path(path).stat().st_size>5000000:raise ValueError('El escenario supera 5 MB')
            s=Scenario.from_dict(json.loads(Path(path).read_text(encoding='utf-8-sig')))
            self.replace(s,Path(path));self.statusBar().showMessage('Escenario cargado: '+path)
        except (OSError,ValueError,TypeError,KeyError) as exc:QMessageBox.critical(self,'Escenario inválido',str(exc))

    def calculate_job(self):
        self.config_changed();self.controller.start(self.scenario,self.caps);self.refresh()

    def run_experiments(self):
        try:
            seeds=[int(s.strip()) for s in self.seeds.text().split(',')]
            if not seeds or len(seeds)>100 or len(set(seeds))!=len(seeds) or any(s<0 or s>2147483647 for s in seeds):raise ValueError()
        except ValueError:QMessageBox.warning(self,'Semillas inválidas','Introduce de 1 a 100 semillas enteras distintas entre 0 y 2147483647, separadas por comas.');return
        self.experiment_table.setRowCount(0);self.controller.start(self.scenario,self.caps,seeds);self.refresh()

    def job_update(self,snapshot):
        self.job_state=snapshot.state
        if snapshot.results:self.results=snapshot.results;self.result_scenario=self.controller.scenario.clone() if self.controller.scenario else None
        self.refresh()
        self.progress.setVisible(snapshot.state=='running')
        if snapshot.progress_percent is None:self.progress.setRange(0,0);self.progress.setTextVisible(False)
        else:self.progress.setRange(0,100);self.progress.setValue(round(snapshot.progress_percent));self.progress.setTextVisible(True)
        message=' · '.join(snapshot.messages)
        if snapshot.error:
            extras=list(dict.fromkeys(m for m in snapshot.messages if m!=snapshot.error.message))
            message=snapshot.error.message+(' · '+' · '.join(extras) if extras else '')
        if snapshot.metadata.get('engine_result',{}).get('red',{}).get('fuente')=='sintetica':message='PRUEBA SINTÉTICA EXPLÍCITA · '+message
        if not message:message=STATES[snapshot.state]
        self.result_message.setText(message);self.statusBar().showMessage(message)
        if snapshot.experiment_rows:
            self.experiment_table.setRowCount(len(snapshot.experiment_rows))
            for row,item in enumerate(snapshot.experiment_rows):
                for col,key in enumerate(['seed','method','state','cost','gap_percent','valid','duration_seconds','message']):
                    self.experiment_table.setItem(row,col,QTableWidgetItem(str(item.get(key,'—'))))
        self.refresh_history()

    def render_results(self):
        s=self.result_scenario or self.scenario
        points={p.id:chr(65+i)+' · '+p.name for i,p in enumerate(s.destinations)}
        if s.base:points[s.base.id]='H · '+s.base.name
        for m,card in self.result_cards.items():
            result=next((r for r in self.results if r.method==m),None)
            card.setVisible(m in self.scenario.config.methods or result is not None)
            card.update_result(result,points)
        self.results_subtitle.setText(f'{s.name} · Semilla {s.config.seed} · Resultados del backend' if self.results else 'Sin resultados · Un recorrido con regreso a la base')
        if not self.results:self.result_message.setText('Backend no conectado. Conecta un servicio para calcular y comparar recorridos.' if not self.caps.connected else 'Sin resultados. Configura el escenario y solicita un cálculo.')
        if self.map_ready:self.map.bridge.routes.emit(json.dumps([asdict(r) for r in self.results],ensure_ascii=False),json.dumps(self.visibility))

    def toggle_route(self,method,visible):
        self.visibility[method]=visible;self.render_results()

    def history_rows(self):
        rows=[]
        for i,h in enumerate(self.controller.history):
            snapshot=h['snapshot'];results=snapshot['results'] or [{}]
            for r in results:
                rows.append((i,[h['received_at'],(h['scenario'] or {}).get('name',''),STATES[snapshot['state']],r.get('method','—'),r.get('cost'),r.get('gap_percent'),r.get('valid'),r.get('duration_seconds')]))
        return rows

    def refresh_history(self):
        rows=self.history_rows();self.history_table.setRowCount(len(rows))
        for row,(index,values) in enumerate(rows):
            for col,value in enumerate(values):
                item=QTableWidgetItem('—' if value is None else str(value));item.setData(Qt.ItemDataRole.UserRole,index);self.history_table.setItem(row,col,item)

    def history_selection(self):
        items=self.history_table.selectedItems()
        if items:self.history_detail.setPlainText(json.dumps(self.controller.history[items[0].data(Qt.ItemDataRole.UserRole)],ensure_ascii=False,indent=2))

    def export_history(self):
        if not self.controller.history:QMessageBox.information(self,'Sin resultados','Todavía no se recibieron resultados del backend.');return
        path,kind=QFileDialog.getSaveFileName(self,'Exportar historial','resultados-qrescate.json','JSON (*.json);;CSV (*.csv)')
        if not path:return
        try:
            if kind.startswith('CSV') or path.lower().endswith('.csv'):
                output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(['received_at_utc','scenario','kind','job_id','state','seed','method','cost','unit','gap_percent','valid','duration_seconds','visit_order_json','geometry_json','messages','error_json','method_status','metadata_json'])
                for values in self.export_rows():
                    # Spreadsheet-safe export, including scenario names from imported JSON.
                    writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values])
                Path(path).write_text(output.getvalue(),encoding='utf-8-sig')
            else:Path(path).write_text(json.dumps({'schema_version':1,'history':self.controller.history},ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            self.statusBar().showMessage('Historial exportado: '+path)
        except (OSError,ValueError) as exc:QMessageBox.critical(self,'Error al exportar',str(exc))

    def export_rows(self):
        for h in self.controller.history:
            s=h['scenario'] or {};snap=h['snapshot']
            entries=snap.get('experiment_rows') or snap.get('results') or [{}]
            for result in entries:
                messages=result.get('messages',[])
                if result.get('message'):messages=messages+[result['message']]
                yield [h['received_at'],s.get('name',''),h['kind'],snap['job_id'],result.get('state',snap['state']),result.get('seed',s.get('config',{}).get('seed')),
                       result.get('method'),result.get('cost'),result.get('unit',''),result.get('gap_percent'),result.get('valid'),result.get('duration_seconds'),
                       json.dumps(result.get('visit_order',[]),ensure_ascii=False),json.dumps(result.get('geometry'),ensure_ascii=False),
                       ' · '.join(messages+snap.get('messages',[])),json.dumps(snap.get('error'),ensure_ascii=False),
                       result.get('status',''),json.dumps(snap.get('metadata',{}),ensure_ascii=False)]

    def closeEvent(self,event):
        if self.controller.busy:
            answer=QMessageBox.question(self,'Cálculo activo','¿Cancelar el cálculo y cerrar la aplicación?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if answer!=QMessageBox.StandardButton.Yes:event.ignore();return
            self.controller.shutdown();self.controller.busy=False
        if not self.allow_replace():event.ignore();return
        self.controller.shutdown();event.accept()
