from window import MainWindowUI, QApplication
import sys



class App(MainWindowUI):
    def __init__(self):
        super().__init__()
        self.initUI()

    def start(self, app):
        self.show()
        sys.exit(app.exec())



if __name__ == "__main__":
    app = QApplication(sys.argv)
    App().start(app)