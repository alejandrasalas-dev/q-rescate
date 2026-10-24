from pathlib import Path
import re
from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QVBoxLayout, QHBoxLayout

PATHS = {
 'home':'<path d="M3 11 12 3l9 8M6 10v11h5v-7h3v7h4V10"/>',
 'map':'<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3ZM9 3v15M15 6v15"/>',
 'flask':'<path d="M9 3h6M10 3v7L4 20h16l-6-10V3M8 14h8"/>',
 'chart':'<path d="M5 20v-6M12 20V8M19 20V3" stroke-width="4"/>',
 'help':'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 4 3v2M12 17h.01"/>',
 'pin':'<path d="M12 22s8-8 8-14a8 8 0 0 0-16 0c0 6 8 14 8 14Z"/><circle cx="12" cy="8" r="2"/>',
 'ban':'<circle cx="12" cy="12" r="9"/><path d="m6 18 12-12"/>',
 'circle':'<circle cx="12" cy="12" r="9" stroke-dasharray="4 3"/>',
 'route':'<circle cx="5" cy="18" r="3"/><circle cx="12" cy="5" r="3"/><circle cx="20" cy="18" r="3"/><path d="m7 15 4-7m3 0 4 7M8 18h9"/>',
 'ambulance':'<path d="M2 7h12v12H2ZM14 11h4l4 5v3h-8M6 10h5M8.5 8v5"/><circle cx="6" cy="20" r="2"/><circle cx="18" cy="20" r="2"/>',
 'file':'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 7h8M8 12h8M8 17h6"/>',
 'download':'<path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4"/>',
 'logo':'<path d="m12 2 9 5v10l-9 5-9-5V7Z"/><path d="m12 6 5 3v6l-5 3-5-3V9ZM12 10v8m0-5 9 4"/>',
}

def icon(name, color='#657186', size=24):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
    pix=QPixmap(size*2,size*2);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix);QSvgRenderer(QByteArray(svg.encode())).render(painter);painter.end();pix.setDevicePixelRatio(2)
    return QIcon(pix)

def label(text, role='', wrap=False):
    w=QLabel(text);w.setWordWrap(wrap)
    if role:w.setObjectName(role)
    w.setTextFormat(Qt.TextFormat.PlainText)
    return w

def button(text, fn=None, name='', glyph=None, color='#657186'):
    b=QPushButton(text)
    if name:b.setObjectName(name)
    if glyph:b.setIcon(icon(glyph,color));b.setIconSize(QSize(19,19))
    if fn:b.clicked.connect(fn)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b

def frame(name='card'):
    f=QFrame();f.setObjectName(name);return f

class StatCard(QFrame):
    def __init__(self, title, glyph, color):
        super().__init__();self.setObjectName('card')
        row=QHBoxLayout(self);row.setContentsMargins(17,11,15,11);row.setSpacing(15)
        im=QLabel();im.setPixmap(icon(glyph,color,30).pixmap(30,30));row.addWidget(im)
        col=QVBoxLayout();col.setSpacing(1);col.addWidget(label(title,'muted'))
        self.value=label('0','stat');col.addWidget(self.value);row.addLayout(col,1)

class ResultCard(QFrame):
    def __init__(self, title, color):
        super().__init__();self.setObjectName('resultCard')
        self.setStyleSheet(f'QFrame#resultCard{{border-left:6px solid {color};}}')
        root=QVBoxLayout(self);root.setContentsMargins(16,10,12,9);root.setSpacing(6)
        row=QHBoxLayout();im=QLabel();im.setPixmap(icon('route',color,25).pixmap(25,25));row.addWidget(im)
        title_label=label(title,'methodTitle');title_label.setStyleSheet(f'color:{color}');row.addWidget(title_label);row.addStretch();root.addLayout(row)
        metrics=QHBoxLayout();self.values=[]
        for title in ('Costo','Ruta válida','Gap'):
            col=QVBoxLayout();col.setSpacing(1);caption=label(title,'muted');caption.setAlignment(Qt.AlignmentFlag.AlignCenter);col.addWidget(caption);v=label('—','metric');v.setAlignment(Qt.AlignmentFlag.AlignCenter);col.addWidget(v);metrics.addLayout(col,1);self.values.append(v)
        root.addLayout(metrics)
        self.detail=label('Sin resultados','muted',True);root.addWidget(self.detail)

    def update_result(self, result, points):
        if result is None:
            for v in self.values:v.setText('—')
            self.detail.setText('Sin resultados');return
        fmt=lambda v:'—' if v is None else f'{v:g}'
        self.values[0].setText(fmt(result.cost)+(f' {result.unit}' if result.unit else ''))
        self.values[1].setText('—' if result.valid is None else ('✓ Sí' if result.valid else '✕ No'))
        if result.metadata.get('covers_all_destinations') is False:self.values[1].setText('Parcial')
        self.values[1].setStyleSheet('color:'+('#10a16a' if result.valid else '#d34b42'))
        self.values[2].setText(fmt(result.gap_percent)+(' %' if result.gap_percent is not None else ''))
        order=' → '.join(points.get(p,p) for p in result.visit_order)
        duration='Duración: '+fmt(result.duration_seconds)+(' s' if result.duration_seconds is not None else '')
        self.detail.setText((result.status.upper()+' · ' if result.status!='ok' else '')+duration+' · '+('Visitas: '+order if order else 'Orden no informado')+('\n'+' · '.join(result.messages) if result.messages else ''))

STYLE='''
QWidget { font-family:"Segoe UI"; font-size:14px; color:#142344; }
QMainWindow,QWidget#shell { background:#f6f9fd; }
QWidget#panelContent {background:#ffffff;}
QFrame#sidebar {background:#f5faff;border-right:1px solid #e6edf4;}
QFrame#card,QFrame#panel,QFrame#results,QFrame#resultCard {background:#fff;border:1px solid #e2e7ef;border-radius:7px;}
QFrame#mapFrame {background:#eaf1ed;border:1px solid #e1e7ee;border-radius:7px;}
QLabel#heading {font-size:24px;font-weight:700;color:#0e1d42;}
QLabel#section {font-size:20px;font-weight:700;color:#0e1d42;}
QLabel#brand {font-size:21px;font-weight:700;color:#0e1d42;}
QLabel#muted {color:#68758a;font-size:13px;}
QLabel#subtitle {color:#637087;font-size:14px;}
QLabel#stat {font-size:22px;font-weight:700;}
QLabel#metric {font-size:22px;font-weight:700;}
QLabel#methodTitle {font-size:15px;font-weight:700;}
QLabel#badge {background:#fff0c9;color:#81531b;border-radius:4px;padding:6px 10px;font-size:10px;font-weight:600;}
QPushButton {background:#fff;border:1px solid #dbe2eb;border-radius:5px;padding:8px 11px;min-height:17px;}
QPushButton:hover {background:#edf6fc;border-color:#9ac6e9;}
QPushButton:pressed {background:#dcedfa;}
QPushButton:disabled {color:#7b8f9a;background:#ecf2f5;border-color:#e2e8ed;}
QPushButton#primary {background:#0096a6;border:1px solid #008b9c;color:white;font-weight:700;padding:12px;}
QPushButton#primary:hover {background:#008a9a;}
QPushButton#primary:disabled {background:#7cb8bf;border-color:#7cb8bf;color:#f7ffff;}
QPushButton#nav {border:0;background:transparent;text-align:left;padding:12px 17px;border-radius:3px;}
QPushButton#nav:checked {background:#e1f1ff;color:#1357a5;font-weight:600;}
QPushButton#nav:hover {background:#eaf3fa;}
QPushButton#tool {font-size:11px;padding:7px 9px;background:#fffffff5;}
QPushButton#tiny {border:0;background:transparent;padding:2px;min-width:20px;color:#75849b;}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QListWidget,QTableWidget,QPlainTextEdit {background:white;border:1px solid #d9e0e9;border-radius:5px;padding:7px;selection-background-color:#dceefe;}
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus {border:1px solid #38a9b2;}
QCheckBox {spacing:7px;}
QCheckBox::indicator {width:18px;height:18px;border-radius:3px;border:1px solid #b9c6d6;background:white;}
QCheckBox::indicator:checked {background:#1673e6;border-color:#1673e6;image:url("CHECK_ASSET");}
QCheckBox#qaoa::indicator:checked {background:#8025dc;border-color:#8025dc;}
QCheckBox#greedy::indicator:checked {background:#e99b20;border-color:#e99b20;}
QGroupBox {border:1px solid #e4e9f1;border-radius:5px;margin-top:10px;padding-top:12px;}
QGroupBox::title {subcontrol-origin:margin;left:10px;padding:0 4px;font-weight:600;}
QScrollArea {border:0;background:transparent;}
QScrollBar:vertical {width:7px;background:#f1f5f8;}
QScrollBar::handle:vertical {background:#cbd7e3;min-height:30px;border-radius:3px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QHeaderView::section {background:#f1f6fc;border:0;padding:8px;color:#41536c;font-weight:600;}
QToolTip {background:#fff;border:1px solid #ccd6e1;padding:6px;color:#142344;}
QStatusBar {background:#f6f9fd;color:#64728a;}
'''
STYLE=STYLE.replace('CHECK_ASSET',(Path(__file__).parent/'assets'/'check.svg').as_posix())

def theme_style(theme):
    if theme!='dark':return STYLE
    colors={
        '#142344':'#e4edf9','#f6f9fd':'#121c2c','#ffffff':'#1c293e','#fff':'#1c293e',
        '#f5faff':'#162237','#e6edf4':'#2e4059','#e2e7ef':'#34455d','#eaf1ed':'#182538',
        '#e1e7ee':'#34455d','#0e1d42':'#f0f5ff','#68758a':'#acbbcf','#637087':'#b2bfd2',
        '#fff0c9':'#4b3e24','#81531b':'#f3d58a','#dbe2eb':'#3b4d66','#edf6fc':'#273b56',
        '#9ac6e9':'#4c799e','#dcedfa':'#314b68','#7b8f9a':'#94a3b8','#ecf2f5':'#243247',
        '#e2e8ed':'#3a4a60','#e1f1ff':'#233e61','#1357a5':'#a4d4ff','#eaf3fa':'#22354d',
        '#75849b':'#afbdd2','#fffffff5':'#1c293ef5','#d9e0e9':'#41516a','#dceefe':'#2e4b71',
        '#b9c6d6':'#647793','#e4e9f1':'#34455d','#f1f5f8':'#182538','#cbd7e3':'#52657e',
        '#f1f6fc':'#24344c','#41536c':'#d4e0f0','#ccd6e1':'#435770','#64728a':'#a9bad0',
        '#7cb8bf':'#375e69',
    }
    result=re.sub(r'#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b',lambda m:colors.get(m.group().lower(),m.group()),STYLE)
    return result.replace('background:white','background:#1c293e')
