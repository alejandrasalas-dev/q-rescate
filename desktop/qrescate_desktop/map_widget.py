import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from .geography import BOUNDARY

class MapPage(QWebEnginePage):
    def acceptNavigationRequest(self,url,kind,main_frame):
        if main_frame and url.scheme() in ('http','https'):
            if kind==QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url,kind,main_frame)

class Bridge(QObject):
    scene = Signal(str)
    mode = Signal(str)
    selection = Signal(str)
    routes = Signal(str, str)
    locked = Signal(bool)
    theme = Signal(str)
    received = Signal(dict)

    @Slot(str)
    def event(self, payload):
        try:
            if len(payload) > 20000:
                return
            data = json.loads(payload)
            if isinstance(data, dict):
                self.received.emit(data)
        except (ValueError, TypeError):
            pass

class MapView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPage(MapPage(self))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.bridge = Bridge(self)
        self.channel = QWebChannel(self.page())
        self.channel.registerObject('bridge', self.bridge)
        self.page().setWebChannel(self.channel)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        assets=Path(__file__).parent/'assets'
        html=(assets/'map.html').read_text(encoding='utf-8').replace('__SATIPO_GEOJSON__',json.dumps(BOUNDARY))
        self.setHtml(html,QUrl.fromLocalFile(str(assets)+'/' ))

    def command(self, function, *args):
        # Function names are fixed by callers, user strings are always JSON encoded.
        if function not in ('province', 'focusObject'):
            raise ValueError('Comando de mapa inválido')
        self.page().runJavaScript(function+'('+','.join(json.dumps(a) for a in args)+');')
