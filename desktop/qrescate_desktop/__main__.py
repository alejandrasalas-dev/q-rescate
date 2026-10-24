import sys
from PySide6.QtWidgets import QApplication
from .window import MainWindow

def main():
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setApplicationName('Q-Rescate');app.setOrganizationName('Q-Rescate')
    window=MainWindow();window.show();return app.exec()

if __name__=='__main__':
    sys.exit(main())
