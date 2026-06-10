import      os
import      sys

from        PyQt5.QtWidgets import QApplication, QWidget, QMenu
from        PyQt5.QtCore import QTimer

import      psutil


class MainClass(QWidget):
    def __init__(self):
        super().__init__()
        
        self._create_gui()

        self.debug_timer = QTimer()
        self.debug_timer.timeout.connect(self.log_stats)
        self.debug_timer.start(500)

        #SYSTEM MONITORING
        self.process = psutil.Process(os.getpid())

    def log_stats(self):
        count = len(self.children())
        mem_mb = self.process.memory_info().rss / (1024 * 1024)
        print(f"RAM: {mem_mb:.2f} MB | Qt Objects: {count}")

    def _create_gui(self):
        self.menu = QMenu(self)
        self.Movie_menu = QMenu("menu1", self)
        self.Movie_menu.addAction('option1')
        self.Movie_menu.addAction('option2')
        self.Movie_menu.addAction('option3')
        self.menu.addMenu(self.Movie_menu)
                
        menu_stylesheet = """
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
                padding: 2px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QMenu::separator {
                background-color: #444444;
                height: 1px;
                margin: 2px 0px;
            }
        """
        self.menu.setStyleSheet(menu_stylesheet)

        self.setWindowTitle("Leakymenu")
        self.setFixedSize(357, 342)

    def mouseDoubleClickEvent(self, event):
        self.menu.popup(event.globalPos())


app = QApplication(sys.argv)
main = MainClass()
main.show()
app.exec()
