import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QAction, QToolBar,
    QColorDialog, QMessageBox
)
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QPolygonF, QKeySequence
)
from PyQt5.QtCore import Qt, QPointF, QRectF


# ======================================================================
# 1. СВОЙ КОНТЕЙНЕР (из ЛР3) — динамический массив
# ======================================================================
class ShapeContainer:
    def __init__(self):
        self._capacity = 4
        self._buffer = [None] * self._capacity
        self._size = 0

    def _grow(self):
        new_cap = self._capacity * 2
        new_buf = [None] * new_cap
        for i in range(self._size):
            new_buf[i] = self._buffer[i]
        self._buffer = new_buf
        self._capacity = new_cap

    def append(self, item):
        if self._size >= self._capacity:
            self._grow()
        self._buffer[self._size] = item
        self._size += 1

    def remove(self, item):
        for i in range(self._size):
            if self._buffer[i] is item:
                self.remove_at(i)
                return
        raise ValueError("Объект не найден")

    def remove_at(self, index):
        if index < 0 or index >= self._size:
            raise IndexError
        for i in range(index, self._size - 1):
            self._buffer[i] = self._buffer[i + 1]
        self._buffer[self._size - 1] = None
        self._size -= 1

    def __getitem__(self, index):
        if index < 0:
            index += self._size
        if index < 0 or index >= self._size:
            raise IndexError
        return self._buffer[index]

    def __len__(self):
        return self._size

    def __iter__(self):
        for i in range(self._size):
            yield self._buffer[i]


# ======================================================================
# 2. ИЕРАРХИЯ ФИГУР
# ======================================================================
class Shape:
    def __init__(self, x, y, w, h, color):
        self._x = float(x)
        self._y = float(y)
        self._w = max(1.0, float(w))
        self._h = max(1.0, float(h))
        self._color = QColor(color)
        self.selected = False

    @property
    def x(self): return self._x
    @x.setter
    def x(self, v): self._x = float(v)

    @property
    def y(self): return self._y
    @y.setter
    def y(self, v): self._y = float(v)

    @property
    def w(self): return self._w
    @w.setter
    def w(self, v): self._w = max(1.0, float(v))

    @property
    def h(self): return self._h
    @h.setter
    def h(self, v): self._h = max(1.0, float(v))

    @property
    def color(self): return self._color
    @color.setter
    def color(self, c): self._color = QColor(c)

    def bounding_rect(self):
        return QRectF(self._x, self._y, self._w, self._h)

    def contains(self, point):
        return self.bounding_rect().contains(point)

    def move_by(self, dx, dy):
        self._x += dx
        self._y += dy

    def resize_by(self, dw, dh):
        self._w = max(1.0, self._w + dw)
        self._h = max(1.0, self._h + dh)

    def is_within(self, bounds):
        r = self.bounding_rect()
        return (r.left()   >= bounds.left() and
                r.top()    >= bounds.top() and
                r.right()  <= bounds.right() and
                r.bottom() <= bounds.bottom())

    def try_move(self, dx, dy, bounds):
        ox, oy = self._x, self._y
        self.move_by(dx, dy)
        if not self.is_within(bounds):
            self._x, self._y = ox, oy
            return False
        return True

    def try_resize(self, dw, dh, bounds):
        ow, oh = self._w, self._h
        self.resize_by(dw, dh)
        if not self.is_within(bounds):
            self._w, self._h = ow, oh
            return False
        return True

    def draw(self, painter):
        painter.setBrush(QBrush(self._color))
        painter.setPen(QPen(Qt.black, 1))
        self._draw_shape(painter)

    def _draw_shape(self, painter):
        raise NotImplementedError

    @classmethod
    def display_name(cls): return "Фигура"


class Rectangle(Shape):
    def _draw_shape(self, painter):
        painter.drawRect(self.bounding_rect())

    @classmethod
    def display_name(cls): return "Прямоугольник"


class Square(Rectangle):
    def __init__(self, x, y, w, h, color):
        size = max(w, h)
        super().__init__(x, y, size, size, color)

    def resize_by(self, dw, dh):
        d = dw if abs(dw) >= abs(dh) else dh
        super().resize_by(d, d)

    @classmethod
    def display_name(cls): return "Квадрат"


class Ellipse(Shape):
    def _draw_shape(self, painter):
        painter.drawEllipse(self.bounding_rect())

    @classmethod
    def display_name(cls): return "Эллипс"


class Circle(Ellipse):
    def __init__(self, x, y, w, h, color):
        size = max(w, h)
        super().__init__(x, y, size, size, color)

    def resize_by(self, dw, dh):
        d = dw if abs(dw) >= abs(dh) else dh
        super().resize_by(d, d)

    @classmethod
    def display_name(cls): return "Круг"


class Triangle(Shape):
    def _draw_shape(self, painter):
        r = self.bounding_rect()
        pts = QPolygonF([
            QPointF(r.left(),  r.bottom()),
            QPointF(r.right(), r.bottom()),
            QPointF(r.center().x(), r.top()),
        ])
        painter.drawPolygon(pts)

    @classmethod
    def display_name(cls): return "Треугольник"


class Line(Shape):
    def _draw_shape(self, painter):
        r = self.bounding_rect()
        painter.drawLine(r.topLeft(), r.bottomRight())

    @classmethod
    def display_name(cls): return "Отрезок"


# ======================================================================
# 3. РАБОЧАЯ ОБЛАСТЬ
# ======================================================================
class EditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shapes = ShapeContainer()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)
        self._drag_start = None
        self._drag_originals = []
        self.MOVE_STEP = 1
        self.FAST_STEP = 10
        self.MARGIN = 10

    def bounds(self):
        m = self.MARGIN
        return QRectF(m, m, max(1, self.width() - 2 * m), max(1, self.height() - 2 * m))

    def _is_overlapping(self, shape):
        """Проверяет, пересекается ли фигура с уже существующими."""
        for other in self.shapes:
            if other.bounding_rect().intersects(shape.bounding_rect()):
                return True
        return False

    def add_shape(self, shape_class):
        b = self.bounds()
        
        # 1. Создаем фигуру, чтобы узнать её реальные размеры 
        # (квадрат и круг могут изменить переданные 80x60 на 80x80)
        s = shape_class(0, 0, 80.0, 60.0, Qt.gray)
        w, h = s.w, s.h
        
        gap = 20  # отступ между фигурами
        cols = max(1, int((b.width() - gap) // (w + gap)))
        
        placed = False
        # 2. Ищем свободную ячейку в сетке
        # Берем запас (+50), на случай если какие-то фигуры были удалены и остались "дырки"
        for idx in range(len(self.shapes) + 50):
            col = idx % cols
            row = idx // cols
            
            x = b.left() + gap + col * (w + gap)
            y = b.top() + gap + row * (h + gap)
            
            s.x = x
            s.y = y
            
            # Если фигура влезает в экран и не пересекается с другими — оставляем тут
            if s.is_within(b) and not self._is_overlapping(s):
                placed = True
                break
                
        # 3. Если сетка заполнена (или не хватило места), ставим в центр
        if not placed:
            s.x = b.center().x() - w / 2
            s.y = b.center().y() - h / 2
            
        # Финальная страховка от выхода за границы
        if not s.is_within(b):
            s.x = b.left() + gap
            s.y = b.top() + gap
            
        self.shapes.append(s)
        self.update()

    def delete_selected(self):
        for s in [s for s in self.shapes if s.selected]:
            self.shapes.remove(s)
        self.update()

    def select_all(self):
        for s in self.shapes:
            s.selected = True
        self.update()

    def deselect_all(self):
        for s in self.shapes:
            s.selected = False
        self.update()

    def set_selected_color(self, color):
        for s in self.shapes:
            if s.selected:
                s.color = color
        self.update()

    def _move_selected(self, dx, dy):
        b = self.bounds()
        for s in self.shapes:
            if s.selected:
                s.try_move(dx, dy, b)
        self.update()

    def _resize_selected(self, dw, dh):
        b = self.bounds()
        for s in self.shapes:
            if s.selected:
                s.try_resize(dw, dh, b)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), Qt.white)

        p.setPen(QPen(QColor(210, 210, 210), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.bounds())

        for s in self.shapes:
            s.draw(p)
            if s.selected:
                p.setPen(QPen(Qt.blue, 1, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRect(s.bounding_rect().adjusted(-3, -3, 3, 3))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = QPointF(event.pos())

        hit = None
        for i in range(len(self.shapes) - 1, -1, -1):
            if self.shapes[i].contains(pos):
                hit = self.shapes[i]
                break

        additive = bool(event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))

        if hit is None:
            if not additive:
                self.deselect_all()
        else:
            if additive:
                hit.selected = not hit.selected
            elif not hit.selected:
                self.deselect_all()
                hit.selected = True

        self.update()

        if hit is not None and hit.selected:
            self._drag_start = pos
            self._drag_originals = [(s, s.x, s.y) for s in self.shapes if s.selected]

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            return
        delta = QPointF(event.pos()) - self._drag_start
        dx, dy = self._clamp_drag(delta.x(), delta.y())
        for s, ox, oy in self._drag_originals:
            s.x = ox + dx
            s.y = oy + dy
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = None
            self._drag_originals = []

    def _clamp_drag(self, dx, dy):
        b = self.bounds()
        for s, ox, oy in self._drag_originals:
            if ox + dx < b.left(): dx = b.left() - ox
            if ox + dx + s.w > b.right(): dx = b.right() - ox - s.w
            if oy + dy < b.top(): dy = b.top() - oy
            if oy + dy + s.h > b.bottom(): dy = b.bottom() - oy - s.h
        return dx, dy

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            return
        if key == Qt.Key_A and (mods & Qt.ControlModifier):
            self.select_all()
            return
        if key == Qt.Key_Escape:
            self.deselect_all()
            return

        step = self.FAST_STEP if (mods & Qt.ShiftModifier) else self.MOVE_STEP
        dx = dy = 0
        if key == Qt.Key_Left: dx = -step
        elif key == Qt.Key_Right: dx = step
        elif key == Qt.Key_Up: dy = -step
        elif key == Qt.Key_Down: dy = step
        else:
            super().keyPressEvent(event)
            return

        if mods & Qt.ControlModifier:
            self._resize_selected(dx, dy)
        else:
            self._move_selected(dx, dy)
  

# ======================================================================
# 4. ГЛАВНОЕ ОКНО
# ======================================================================
class MainWindow(QMainWindow):
    SHAPE_CLASSES = [Rectangle, Square, Ellipse, Circle, Triangle, Line]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Визуальный редактор — ЛР4")
        self.resize(1000, 700)

        self.editor = EditorWidget(self)
        self.setCentralWidget(self.editor)
        self.editor.setFocus()

        self._actions = {}
        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()

    def _build_actions(self):
        for cls in self.SHAPE_CLASSES:
            a = QAction(f"Добавить {cls.display_name().lower()}", self)
            a.triggered.connect(lambda checked=False, c=cls: self.editor.add_shape(c))
            self._actions[f"add_{cls.__name__}"] = a

        a = QAction("Цвет выделенных…", self)
        a.triggered.connect(self._on_change_color)
        self._actions["color"] = a

        a = QAction("Удалить выделенные", self)
        a.setShortcut(QKeySequence(Qt.Key_Delete))
        a.triggered.connect(self.editor.delete_selected)
        self._actions["delete"] = a

        a = QAction("Выделить всё", self)
        a.setShortcut(QKeySequence.SelectAll)
        a.triggered.connect(self.editor.select_all)
        self._actions["select_all"] = a

        a = QAction("Снять выделение", self)
        a.triggered.connect(self.editor.deselect_all)
        self._actions["deselect"] = a

        a = QAction("Выход", self)
        a.setShortcut(QKeySequence.Quit)
        a.triggered.connect(self.close)
        self._actions["quit"] = a

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("Файл")
        file_menu.addAction(self._actions["quit"])

        create_menu = mb.addMenu("Создать")
        for cls in self.SHAPE_CLASSES:
            create_menu.addAction(self._actions[f"add_{cls.__name__}"])

        edit_menu = mb.addMenu("Правка")
        edit_menu.addAction(self._actions["select_all"])
        edit_menu.addAction(self._actions["deselect"])
        edit_menu.addSeparator()
        edit_menu.addAction(self._actions["color"])
        edit_menu.addSeparator()
        edit_menu.addAction(self._actions["delete"])

        help_menu = mb.addMenu("Справка")
        a = QAction("Управление…", self)
        a.triggered.connect(self._show_help)
        help_menu.addAction(a)

    def _build_toolbar(self):
        tb = QToolBar("Инструменты", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        for cls in self.SHAPE_CLASSES:
            tb.addAction(self._actions[f"add_{cls.__name__}"])
        tb.addSeparator()
        tb.addAction(self._actions["color"])
        tb.addSeparator()
        tb.addAction(self._actions["delete"])

    def _build_statusbar(self):
        self.statusBar().showMessage(
            "Стрелки — перемещение | Ctrl+стрелки — размер | "
            "Shift — ускоренно | Delete — удалить | Ctrl+A — выделить всё"
        )

    def _on_change_color(self):
        selected = [s for s in self.editor.shapes if s.selected]
        if not selected:
            QMessageBox.information(self, "Цвет", "Сначала выделите хотя бы один объект.")
            return
        c = QColorDialog.getColor(selected[0].color, self, "Выбор цвета")
        if c.isValid():
            self.editor.set_selected_color(c)

    def _show_help(self):
        QMessageBox.information(
            self, "Управление",
            "Мышь:\n"
            "• ЛКМ по объекту — выделить\n"
            "• Shift/Ctrl + ЛКМ — добавить/убрать из выделения\n"
            "• ЛКМ по пустому месту — снять выделение\n"
            "• Перетаскивание — перемещение\n\n"
            "Клавиатура:\n"
            "• Стрелки — сдвиг на 1 пкс\n"
            "• Shift+стрелки — сдвиг на 10 пкс\n"
            "• Ctrl+стрелки — изменение размера\n"
            "• Delete — удалить\n"
            "• Ctrl+A — выделить всё\n"
            "• Esc — снять выделение"
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
