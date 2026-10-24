def main():
    import sys
    import argparse
    import importlib
    from PySide6.QtWidgets import QApplication
    from .window import MainWindow
    from .backend import DisconnectedBackend
    parser=argparse.ArgumentParser()
    parser.add_argument('--disconnected',action='store_true')
    parser.add_argument('--synthetic-test',action='store_true',help='Prueba sintética explícita; nunca reemplaza OSM')
    parser.add_argument('--smoke-test',help='Guardar informe automático de ventana/mapa/motor y cerrar')
    args,_=parser.parse_known_args()
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setApplicationName('Q-Rescate');app.setOrganizationName('Q-Rescate')
    startup_error=None
    backend=DisconnectedBackend()
    if not args.disconnected:
        try:
            for module in ('engine.ejecutor','osmnx','qiskit_optimization','qiskit_algorithms'):
                importlib.import_module(module)
            from .local_backend import LocalBackend
            backend=LocalBackend(source='sintetica' if args.synthetic_test else 'osm')
        except Exception as exc:startup_error=str(exc)
    window=MainWindow(backend);window.show()
    if args.synthetic_test:window.statusBar().showMessage('PRUEBA SINTÉTICA EXPLÍCITA · No son calles reales de OSM.')
    if startup_error:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100,lambda:window.result_message.setText('Backend no disponible: '+startup_error))
    if args.smoke_test:
        from .smoke import install_smoke
        install_smoke(window,args.smoke_test,args.synthetic_test,startup_error)
    return app.exec()

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    import sys
    sys.exit(main())
