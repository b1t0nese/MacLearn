from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QLayout, QTabBar


class _BaseInstanceLoader(QUiLoader):
    def __init__(self, baseinstance=None):
        super().__init__()
        self.baseinstance = baseinstance

    def createWidget(self, class_name, parent=None, name=""):
        if self.baseinstance is not None and parent is None:
            self.baseinstance.setObjectName(name)
            return self.baseinstance
        if class_name == "QTabBar":
            return QTabBar(parent)
        return super().createWidget(class_name, parent, name)


def loadUi(ui_file, baseinstance=None):
    loader = _BaseInstanceLoader(baseinstance)
    widget = loader.load(ui_file)
    if widget is None:
        raise RuntimeError(loader.errorString())
    target = baseinstance if baseinstance is not None else widget
    children = list(widget.children())
    seen = set()
    while children:
        child = children.pop()
        if id(child) in seen:
            continue
        seen.add(id(child))
        if child.objectName():
            setattr(target, child.objectName(), child)
        children.extend(child.children())
        if isinstance(child, QLayout):
            for index in range(child.count()):
                item = child.itemAt(index)
                if item.widget() is not None:
                    children.append(item.widget())
                if item.layout() is not None:
                    children.append(item.layout())
    return widget
