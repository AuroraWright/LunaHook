from qtsymbols import *
import os, re, functools, hashlib, json, math, csv, io, pickle
from traceback import print_exc
import windows, qtawesome, winsharedutils, gobject, platform
from webviewpy import webview_native_handle_kind_t, Webview
from myutils.config import _TR, globalconfig
from myutils.wrapper import Singleton_close, tryprint
from myutils.utils import nowisdark, checkportavailable, checkisusingwine
from gui.dynalang import (
    LLabel,
    LMessageBox,
    LPushButton,
    LAction,
    LGroupBox,
    LFormLayout,
    LTabWidget,
    LStandardItemModel,
    LDialog,
    LMainWindow,
    LToolButton,
)


class FocusCombo(QComboBox):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, e: QWheelEvent) -> None:

        if not self.hasFocus():
            e.ignore()
            return
        else:
            return super().wheelEvent(e)


class SuperCombo(FocusCombo):
    Visoriginrole = Qt.ItemDataRole.UserRole + 1
    Internalrole = Visoriginrole + 1

    def __init__(self, parent=None, static=False) -> None:
        super().__init__(parent)
        self.mo = QStandardItemModel()
        self.static = static
        self.setModel(self.mo)
        self.vu = QListView()
        self.setView(self.vu)

    def addItem(self, item, internal=None):
        item1 = QStandardItem(_TR(item) if not self.static else item)
        item1.setData(item, self.Visoriginrole)
        item1.setData(internal, self.Internalrole)
        self.mo.appendRow(item1)

    def clear(self):
        self.mo.clear()

    def addItems(self, items, internals=None):
        for i, item in enumerate(items):
            iternal = None
            if internals and i < len(internals):
                iternal = internals[i]
            self.addItem(item, iternal)

    def updatelangtext(self):
        if self.static:
            return
        for _ in range(self.mo.rowCount()):
            item = self.mo.item(_, 0)
            item.setData(
                _TR(item.data(self.Visoriginrole)), Qt.ItemDataRole.DisplayRole
            )

    def getIndexData(self, index):
        item = self.mo.item(index, 0)
        return item.data(self.Internalrole)

    def setRowVisible(self, row, vis):
        self.vu.setRowHidden(row, not vis)
        item = self.mo.item(row, 0)
        if vis:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)


class FocusFontCombo(QFontComboBox, FocusCombo):
    pass


class FocusSpinBase(QAbstractSpinBox):

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, e: QWheelEvent) -> None:
        if not self.hasFocus():
            e.ignore()
            return
        else:
            return super().wheelEvent(e)

    def stepBy(self, steps):
        _ = super().stepBy(steps)
        self.stepbysignal.emit(steps)
        return _


class FocusSpin(QSpinBox, FocusSpinBase):
    stepbysignal = pyqtSignal(int)


class FocusDoubleSpin(QDoubleSpinBox, FocusSpinBase):
    stepbysignal = pyqtSignal(int)


class TableViewW(QTableView):
    def __init__(self, *argc, updown=False, copypaste=False) -> None:
        super().__init__(*argc)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.copypaste = copypaste
        self.updown = updown
        if updown or copypaste:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self.showmenu)

    def showmenu(self, pos):
        if not self.currentIndex().isValid():
            return
        menu = QMenu(self)
        up = LAction("上移")
        down = LAction("下移")
        copy = LAction("复制")
        paste = LAction("粘贴")
        if self.updown:
            menu.addAction(up)
            menu.addAction(down)
        if self.copypaste:
            menu.addAction(copy)
            menu.addAction(paste)
        action = menu.exec(self.cursor().pos())
        if action == up:
            self.moverank(-1)
        elif action == down:
            self.moverank(1)
        elif action == copy:
            self.copytable()
        elif action == paste:
            self.pastetable()

    def keyPressEvent(self, e):
        if self.copypaste:
            if e.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if e.key() == Qt.Key.Key_C:
                    self.copytable()
                elif e.key() == Qt.Key.Key_V:
                    self.pastetable()
                else:
                    super().keyPressEvent(e)
            else:
                super().keyPressEvent(e)
        else:
            super().keyPressEvent(e)

    def insertplainrow(self, row=0):
        self.model().insertRow(
            row, [QStandardItem() for _ in range(self.model().columnCount())]
        )

    def dedumpmodel(self, col):

        rows = self.model().rowCount()
        dedump = set()
        needremoves = []
        for row in range(rows):
            if isinstance(col, int):
                k = self.getdata(row, col)
            elif callable(col):
                k = col(row)
            if k == "" or k in dedump:
                needremoves.append(row)
                continue
            dedump.add(k)

        for row in reversed(needremoves):
            self.model().removeRow(row)

    def removeselectedrows(self):
        curr = self.currentIndex()
        if not curr.isValid():
            return []
        row = curr.row()
        col = curr.column()
        skip = []
        for index in self.selectedIndexes():
            if index.row() in skip:
                continue
            skip.append(index.row())
        skip = list(reversed(sorted(skip)))

        for row in skip:
            self.model().removeRow(row)
        row = min(row, self.model().rowCount() - 1)
        self.setCurrentIndex(self.model().index(row, col))
        return skip

    def moverank(self, dy):
        curr = self.currentIndex()
        if not curr.isValid():
            return
        row, col = curr.row(), curr.column()

        model = self.model()
        realws = []
        for _ in range(self.model().columnCount()):
            w = self.indexWidget(self.model().index(row, _))
            if w is None:
                realws.append(None)
                continue
            l: QHBoxLayout = w.layout()
            w = l.takeAt(0).widget()
            realws.append(w)
        target = (row + dy) % model.rowCount()
        model.insertRow(target, model.takeRow(row))
        self.setCurrentIndex(model.index(target, col))
        for _ in range(self.model().columnCount()):
            self.setIndexWidget(self.model().index(target, _), realws[_])
        return row, target

    def indexWidgetX(self, row_or_index, col=None):
        if col is None:
            index: QModelIndex = row_or_index
        else:
            index = self.model().index(row_or_index, col)
        w = self.indexWidget(index)
        if w is None:
            return w
        l: QHBoxLayout = w.layout()
        return l.itemAt(0).widget()

    def inputMethodEvent(self, event: QInputMethodEvent):
        # setindexwidget之后，会导致谜之循环触发，异常；
        # 没有setindexwidget的，会跳转到第一个输入的字母的行，正常，但我不想要。
        pres = event.commitString()
        if not pres:
            super().inputMethodEvent(event)
        else:
            event.accept()

    def setIndexWidget(self, index: QModelIndex, w: QWidget):
        if w is None:
            return
        __w = QWidget()
        __l = QHBoxLayout(__w)
        __l.setContentsMargins(0, 0, 0, 0)
        __l.addWidget(w)
        super().setIndexWidget(index, __w)
        if self.rowHeight(index.row()) < w.height():
            self.setRowHeight(index.row(), w.height())

    def updatelangtext(self):
        m = self.model()
        if isinstance(m, LStandardItemModel):
            m.updatelangtext()

    def getindexdata(self, index):
        return self.model().itemFromIndex(index).text()

    def setindexdata(self, index, data):
        self.model().setItem(index.row(), index.column(), QStandardItem(data))

    def compatiblebool(self, data):
        if isinstance(data, str):
            data = data.lower() == "true"
        elif isinstance(data, bool):
            data = data
        else:
            raise Exception
        return data

    def compatiblejson(self, data):
        if isinstance(data, str):
            data = json.loads(data)
        elif isinstance(data, (list, dict, tuple)):
            data = data
        else:
            raise Exception
        return data

    def getdata(self, row_or_index, col=None):
        if col is None:
            index: QModelIndex = row_or_index
        else:
            index = self.model().index(row_or_index, col)
        _1 = self.model().itemFromIndex(index)
        if not _1:
            return ""
        return self.getindexdata(index)

    def copytable(self) -> str:
        _data = []
        lastrow = -1
        for index in self.selectedIndexes():
            if index.row() != lastrow:
                _data.append([])
                lastrow = index.row()
            data = self.getdata(index)
            if not isinstance(data, str):
                data = json.dumps(data, ensure_ascii=False)
            _data[-1].append(data)
        output = io.StringIO()

        csv_writer = csv.writer(output, delimiter="\t")
        for row in _data:
            csv_writer.writerow(row)
        csv_str = output.getvalue()
        output.close()
        winsharedutils.clipboard_set(csv_str)

    def pastetable(self):
        current = self.currentIndex()
        if not current.isValid():
            return
        string = winsharedutils.clipboard_get()
        try:
            csv_file = io.StringIO(string)
            csv_reader = csv.reader(csv_file, delimiter="\t")
            my_list = list(csv_reader)
            csv_file.close()
            if len(my_list) == 1 and len(my_list[0]) == 1:
                self.setindexdata(current, my_list[0][0])
                return
            for j, line in enumerate(my_list):
                self.insertplainrow(current.row() + 1)
            for j, line in enumerate(my_list):
                for i in range(len(line)):
                    data = line[i]
                    c = current.column() + i
                    if c >= self.model().columnCount():
                        continue
                    self.setindexdata(
                        self.model().index(current.row() + 1 + j, c), data
                    )
        except:
            print_exc()
            self.setindexdata(current, string)


def getQMessageBox(
    parent=None,
    title="",
    text="",
    useok=True,
    usecancel=False,
    okcallback=None,
    cancelcallback=None,
):
    msgBox = LMessageBox(parent)
    msgBox.setWindowTitle((title))
    msgBox.setText((text))
    btn = 0
    if useok:
        btn |= QMessageBox.StandardButton.Ok
    if usecancel:
        btn |= QMessageBox.StandardButton.Cancel

    msgBox.setStandardButtons(btn)
    msgBox.setDefaultButton(QMessageBox.StandardButton.Ok)
    ret = msgBox.exec()

    if ret == QMessageBox.StandardButton.Ok and okcallback:
        okcallback()
    elif ret == QMessageBox.StandardButton.Cancel and cancelcallback:
        cancelcallback()


def findnearestscreen(rect: QRect):
    # QScreen ,distance
    # -1时，是有交集
    # -2时，是被包围
    # >=0时，是不在任何屏幕内
    mindis = 9999999999
    usescreen = QApplication.primaryScreen()
    for screen in QApplication.screens():
        rect1, rect2 = screen.geometry(), rect
        if rect1.contains(rect2):
            return screen, -2
        if rect1.intersects(rect2):
            r = rect1.intersected(rect2)
            area = r.width() * r.width()
            dis = -area
        else:
            distances = []
            distances.append(abs(rect1.right() - rect2.left()))
            distances.append(abs(rect1.left() - rect2.right()))
            distances.append(abs(rect1.bottom() - rect2.top()))
            distances.append(abs(rect1.top() - rect2.bottom()))
            dis = min(distances)
        if dis < mindis:
            mindis = dis
            usescreen = screen
    if mindis < 0:
        mindis = -1
    return usescreen, mindis


class saveposwindow(LMainWindow):
    def __init__(self, parent, poslist=None, flags=None) -> None:
        if flags:
            super().__init__(parent, flags=flags)
        else:
            super().__init__(parent)

        self.poslist = poslist
        if self.poslist:
            usescreen, mindis = findnearestscreen(QRect(poslist[0], poslist[1], 1, 1))
            poslist[2] = max(0, min(poslist[2], usescreen.size().width()))
            poslist[3] = max(0, min(poslist[3], usescreen.size().height()))
            if mindis != -2:
                poslist[0] = min(
                    max(poslist[0], 0), usescreen.size().width() - poslist[2]
                )
                poslist[1] = min(
                    max(poslist[1], 0), usescreen.size().height() - poslist[3]
                )
            self.setGeometry(*poslist)

    def __checked_savepos(self):
        if not self.poslist:
            return
        if windows.IsZoomed(int(self.winId())) != 0:
            return
        # self.isMaximized()会在event结束后才被设置，不符合预期。
        for i, _ in enumerate(self.geometry().getRect()):
            self.poslist[i] = _

    def resizeEvent(self, a0) -> None:
        self.__checked_savepos()

    def moveEvent(self, a0) -> None:
        self.__checked_savepos()

    def closeEvent(self, event: QCloseEvent):
        self.__checked_savepos()


class closeashidewindow(saveposwindow):
    showsignal = pyqtSignal()
    realshowhide = pyqtSignal(bool)

    def __init__(self, parent, poslist=None) -> None:
        super().__init__(parent, poslist)
        self.showsignal.connect(self.showfunction)
        self.realshowhide.connect(self.realshowhidefunction)

    def realshowhidefunction(self, show):
        if show:
            self.showNormal()
        else:
            self.hide()

    def showfunction(self):
        if self.isMinimized():
            self.showNormal()
        elif self.isVisible():
            self.hide()
        else:
            self.show()

    def closeEvent(self, event: QCloseEvent):
        self.hide()
        event.ignore()
        super().closeEvent(event)


def disablecolor(__: QColor):
    if __.rgb() == 0xFF000000:
        return Qt.GlobalColor.gray
    __ = QColor(
        max(0, (__.red() - 64)),
        max(
            0,
            (__.green() - 64),
        ),
        max(0, (__.blue() - 64)),
    )
    return __


class MySwitch(QWidget):
    clicked = pyqtSignal(bool)
    clicksignal = pyqtSignal()

    def event(self, a0: QEvent) -> bool:
        if a0.type() == QEvent.Type.MouseButtonDblClick:
            return True
        elif a0.type() == QEvent.Type.EnabledChange:
            self.setEnabled(not self.isEnabled())
            return True
        elif a0.type() == QEvent.Type.FontChange:
            h = QFontMetricsF(self.font()).height()
            sz = QSize(
                int(1.62 * h * gobject.Consts.btnscale),
                int(h * gobject.Consts.btnscale),
            )
            self.setFixedSize(sz)

        return super().event(a0)

    def click(self):
        self.setChecked(not self.checked)
        self.clicked.emit(self.checked)

    def __init__(self, parent=None, sign=True, enable=True):
        super().__init__(parent)
        self.checked = sign
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicksignal.connect(self.click)
        self.__currv = 0
        if sign:
            self.__currv = 20

        self.animation = QVariantAnimation()
        self.animation.setDuration(80)
        self.animation.setStartValue(0)
        self.animation.setEndValue(20)
        self.animation.valueChanged.connect(self.update11)
        self.animation.finished.connect(self.onAnimationFinished)
        self.enable = enable

    def setEnabled(self, enable):
        self.enable = enable
        self.update()

    def isEnabled(self):
        return self.enable

    def isChecked(self):
        return self.checked

    def setChecked(self, check):
        if check == self.checked:
            return
        self.checked = check
        self.runanime()

    def update11(self):
        self.__currv = self.animation.currentValue()
        self.update()

    def runanime(self):
        self.animation.setDirection(
            QVariantAnimation.Direction.Forward
            if self.checked
            else QVariantAnimation.Direction.Backward
        )
        self.animation.start()

    def getcurrentcolor(self):

        __ = QColor(
            [gobject.Consts.buttoncolor_disable, gobject.Consts.buttoncolor][
                self.checked
            ]
        )
        if not self.enable:
            __ = disablecolor(__)
        return __

    def paintanime(self, painter: QPainter):

        painter.setBrush(self.getcurrentcolor())
        wb = self.width() * 0.1
        hb = self.height() * 0.125
        painter.drawRoundedRect(
            QRectF(
                wb,
                hb,
                self.width() - 2 * wb,
                self.height() - 2 * hb,
            ),
            self.height() / 2 - hb,
            self.height() / 2 - hb,
        )
        r = self.height() * 0.275
        rb = self.height() / 2 - hb - r
        offset = self.__currv * (self.width() - 2 * wb - 2 * r - 2 * rb) / 20
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(
            QPointF(
                (wb + r + rb) + offset,
                (self.height() / 2),
            ),
            r,
            r,
        )

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        self.paintanime(painter)

    def mouseReleaseEvent(self, event) -> None:
        if not self.enable:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        try:
            self.checked = not self.checked
            self.clicked.emit(self.checked)
            self.runanime()
            # 父窗口deletelater
        except:
            pass

    def onAnimationFinished(self):
        pass


class resizableframeless(saveposwindow):
    cursorSet = pyqtSignal(Qt.CursorShape)

    def __init__(self, parent, flags, poslist) -> None:
        super().__init__(parent, poslist, flags)
        self.setMouseTracking(True)

        self._padding = 5
        self.resetflags()

    def setCursor(self, a0):
        super().setCursor(a0)
        self.cursorSet.emit(a0)

    def isdoingsomething(self):
        return (
            self._move_drag
            or self._corner_drag_youxia
            or self._bottom_drag
            or self._top_drag
            or self._corner_drag_zuoxia
            or self._right_drag
            or self._left_drag
            or self._corner_drag_zuoshang
            or self._corner_drag_youshang
        )

    def resetflags(self):
        self._move_drag = False
        self._corner_drag_youxia = False
        self._bottom_drag = False
        self._top_drag = False
        self._corner_drag_zuoxia = False
        self._right_drag = False
        self._left_drag = False
        self._corner_drag_zuoshang = False
        self._corner_drag_youshang = False

    def resizeEvent(self, e):
        pad = self._padding
        w = self.width()
        h = self.height()
        if self._move_drag == False:
            self._right_rect = QRect(w - pad, pad, 2 * pad, h - 2 * pad)
            self._left_rect = QRect(-pad, pad, 2 * pad, h - 2 * pad)
            self._bottom_rect = QRect(pad, h - pad, w - 2 * pad, 2 * pad)
            self._top_rect = QRect(pad, -pad, w - 2 * pad, 2 * pad)
            self._corner_youxia = QRect(w - pad, h - pad, 2 * pad, 2 * pad)
            self._corner_zuoxia = QRect(-pad, h - pad, 2 * pad, 2 * pad)
            self._corner_youshang = QRect(w - pad, -pad, 2 * pad, 2 * pad)
            self._corner_zuoshang = QRect(-pad, -pad, 2 * pad, 2 * pad)
        super().resizeEvent(e)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        gpos = QCursor.pos()
        self.startxp = gpos - self.pos()
        self.starty = gpos.y()
        self.startx = gpos.x()
        self.starth = self.height()
        self.startw = self.width()
        pos = event.pos()
        if self._corner_youxia.contains(pos):
            self._corner_drag_youxia = True
        elif self._right_rect.contains(pos):
            self._right_drag = True
        elif self._left_rect.contains(pos):
            self._left_drag = True
        elif self._top_rect.contains(pos):
            self._top_drag = True
        elif self._bottom_rect.contains(pos):
            self._bottom_drag = True
        elif self._corner_zuoxia.contains(pos):
            self._corner_drag_zuoxia = True
        elif self._corner_youshang.contains(pos):
            self._corner_drag_youshang = True
        elif self._corner_zuoshang.contains(pos):
            self._corner_drag_zuoshang = True
        else:
            self._move_drag = True
            self.move_DragPosition = gpos - self.pos()

    def leaveEvent(self, a0) -> None:
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().leaveEvent(a0)

    def mouseMoveEvent(self, event: QMouseEvent):

        pos = event.pos()
        gpos = QCursor.pos()
        if self._corner_youxia.contains(pos):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self._corner_zuoshang.contains(pos):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self._corner_zuoxia.contains(pos):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif self._corner_youshang.contains(pos):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif self._bottom_rect.contains(pos):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif self._top_rect.contains(pos):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif self._right_rect.contains(pos):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif self._left_rect.contains(pos):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        if self._right_drag:
            self.resize(pos.x(), self.height())
        elif self._corner_drag_youshang:
            self.setGeometry(
                self.x(),
                (gpos - self.startxp).y(),
                pos.x(),
                self.starth - (gpos.y() - self.starty),
            )
        elif self._corner_drag_zuoshang:
            self.setgeokeepminsize(
                (gpos - self.startxp).x(),
                (gpos - self.startxp).y(),
                self.startw - (gpos.x() - self.startx),
                self.starth - (gpos.y() - self.starty),
            )

        elif self._left_drag:
            self.setgeokeepminsize(
                (gpos - self.startxp).x(),
                self.y(),
                self.startw - (gpos.x() - self.startx),
                self.height(),
            )
        elif self._bottom_drag:
            self.resize(self.width(), pos.y())
        elif self._top_drag:
            self.setgeokeepminsize(
                self.x(),
                (gpos - self.startxp).y(),
                self.width(),
                self.starth - (gpos.y() - self.starty),
            )
        elif self._corner_drag_zuoxia:
            x, y, w, h = self.calculatexywh(
                (gpos - self.startxp).x(),
                self.y(),
                self.startw - (gpos.x() - self.startx),
                pos.y(),
            )
            self.setGeometry(x, self.y(), w, h)
        elif self._corner_drag_youxia:
            self.resize(pos.x(), pos.y())
        elif self._move_drag:
            self.move(gpos - self.move_DragPosition)

    def mouseReleaseEvent(self, e: QMouseEvent):
        self.resetflags()

    def setgeokeepminsize(self, *argc):
        self.setGeometry(*self.calculatexywh(*argc))

    def calculatexywh(self, x, y, w, h):
        width = max(w, self.minimumWidth())
        height = max(h, self.minimumHeight())
        x -= width - w
        y -= height - h
        return x, y, width, height


def callbackwrap(d, k, call, _):
    d[k] = _

    if call:
        try:
            call(_)
        except:
            print_exc()


def comboboxcallbackwrap(s: SuperCombo, d, k, call, _):
    _ = s.getIndexData(_)
    d[k] = _

    if call:
        try:
            call(_)
        except:
            print_exc()


def getsimplecombobox(
    lst,
    d=None,
    k=None,
    callback=None,
    fixedsize=False,
    internal=None,
    static=False,
    initial=None,
):
    if d is None:
        d = {}
    if initial is not None:
        d[k] = initial
    s = SuperCombo(static=static)
    s.addItems(lst, internal)

    if internal:
        if len(internal):
            if (k not in d) or (d[k] not in internal):
                d[k] = internal[0]

            s.setCurrentIndex(internal.index(d[k]))
        s.currentIndexChanged.connect(
            functools.partial(comboboxcallbackwrap, s, d, k, callback)
        )
    else:
        if len(lst):
            if (k not in d) or (d[k] >= len(lst)):
                d[k] = 0

            s.setCurrentIndex(d[k])
        s.currentIndexChanged.connect(functools.partial(callbackwrap, d, k, callback))
    if fixedsize:
        s.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return s


def D_getsimplecombobox(
    lst, d, k, callback=None, fixedsize=False, internal=None, static=False
):
    return lambda: getsimplecombobox(lst, d, k, callback, fixedsize, internal, static)


def getlineedit(d, key, callback=None, readonly=False):
    s = QLineEdit()
    s.setText(d[key])
    s.setReadOnly(readonly)
    s.textChanged.connect(functools.partial(callbackwrap, d, key, callback))
    return s


def getspinbox(mini, maxi, d, key, double=False, step=1, callback=None):
    if double:
        s = FocusDoubleSpin()
        s.setDecimals(math.ceil(-math.log10(step)))
    else:
        s = FocusSpin()
        d[key] = int(d[key])
    s.setMinimum(mini)
    s.setMaximum(maxi)
    s.setSingleStep(step)
    s.setValue(d[key])
    s.valueChanged.connect(functools.partial(callbackwrap, d, key, callback))
    return s


def D_getspinbox(mini, maxi, d, key, double=False, step=1, callback=None):
    return lambda: getspinbox(mini, maxi, d, key, double, step, callback)


def getIconButton(callback=None, icon="fa.paint-brush", enable=True, qicon=None):

    b = IconButton(icon, enable, qicon)

    if callback:
        b.clicked_1.connect(callback)

    return b


def D_getIconButton(callback=None, icon="fa.paint-brush", enable=True, qicon=None):
    return lambda: getIconButton(callback, icon, enable, qicon)


def getcolorbutton(
    d,
    key,
    callback=None,
    name=None,
    parent=None,
    icon="fa.paint-brush",
    constcolor=None,
    enable=True,
    qicon=None,
):
    if qicon is None:
        qicon = qtawesome.icon(icon, color=constcolor if constcolor else d[key])
    b = IconButton(None, enable=enable, parent=parent, qicon=qicon)
    if callback:
        b.clicked.connect(callback)
    if name:
        setattr(parent, name, b)
    return b


def D_getcolorbutton(
    d,
    key,
    callback,
    name=None,
    parent=None,
    icon="fa.paint-brush",
    constcolor=None,
    enable=True,
    qicon=None,
):
    return lambda: getcolorbutton(
        d,
        key,
        callback,
        name,
        parent,
        icon,
        constcolor,
        enable,
        qicon,
    )


def yuitsu_switch(parent, configdict, dictobjectn, key, callback, checked):
    dictobject = getattr(parent, dictobjectn)
    if checked:
        for k in dictobject:
            configdict[k]["use"] = k == key
            dictobject[k].setChecked(k == key)
    if callback:
        callback(key, checked)


def getsimpleswitch(
    d, key, enable=True, callback=None, name=None, pair=None, parent=None, default=None
):
    if default:
        if key not in d:
            d[key] = default

    b = MySwitch(sign=d[key], enable=enable)
    b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    b.clicked.connect(functools.partial(callbackwrap, d, key, callback))
    if pair:
        if pair not in dir(parent):
            setattr(parent, pair, {})
        getattr(parent, pair)[name] = b
    elif name:
        setattr(parent, name, b)
    return b


def __getsmalllabel(text):
    __ = LLabel(text)
    __.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    return __


def getsmalllabel(text=""):
    return lambda: __getsmalllabel(text)


def D_getsimpleswitch(
    d, key, enable=True, callback=None, name=None, pair=None, parent=None, default=None
):
    return lambda: getsimpleswitch(
        d, key, enable, callback, name, pair, parent, default
    )


def getColor(color, parent, alpha=False):

    color_dialog = QColorDialog(color, parent)
    if alpha:
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
    if alpha:
        layout = color_dialog.layout()
        clearlayout(layout.itemAt(0).layout().takeAt(0))
        layout = (
            layout.itemAt(0).layout().itemAt(0).layout().itemAt(2).widget().layout()
        )
        layout.takeAt(1).widget().hide()
        layout.takeAt(1).widget().hide()
        layout.takeAt(1).widget().hide()
        layout.takeAt(1).widget().hide()
        layout.takeAt(1).widget().hide()
        layout.takeAt(1).widget().hide()

        layout.takeAt(layout.count() - 1).widget().hide()
        layout.takeAt(layout.count() - 1).widget().hide()
        if not alpha:
            layout.takeAt(layout.count() - 1).widget().hide()
            layout.takeAt(layout.count() - 1).widget().hide()
    if color_dialog.exec_() != QColorDialog.DialogCode.Accepted:
        return QColor()
    return color_dialog.selectedColor()


def selectcolor(
    parent,
    configdict,
    configkey,
    button,
    item=None,
    name=None,
    callback=None,
    alpha=False,
):

    color = getColor(QColor(configdict[configkey]), parent, alpha)
    if not color.isValid():
        return
    if button is None:
        button = getattr(item, name)
    button.setIcon(qtawesome.icon("fa.paint-brush", color=color.name()))
    configdict[configkey] = (
        color.name(QColor.NameFormat.HexArgb) if alpha else color.name()
    )
    if callback:
        try:
            callback()
        except:
            print_exc()


def getboxlayout(
    widgets, lc=QHBoxLayout, margin0=False, makewidget=False, delay=False, both=False
):
    w = QWidget() if makewidget else None
    cp_layout = lc(w)

    def __do(cp_layout, widgets):
        for w in widgets:
            if callable(w):
                w = w()
            elif isinstance(w, str):
                w = LLabel(w)
            if isinstance(w, QWidget):
                cp_layout.addWidget(w)
            elif isinstance(w, QLayout):
                cp_layout.addLayout(w)

    _do = functools.partial(__do, cp_layout, widgets)
    if margin0:
        cp_layout.setContentsMargins(0, 0, 0, 0)
    if not delay:
        _do()
    if delay:
        return w, _do
    if both:
        return w, cp_layout
    if makewidget:
        return w
    return cp_layout


class abstractwebview(QWidget):
    on_load = pyqtSignal(str)
    on_ZoomFactorChanged = pyqtSignal(float)
    html_limit = 2 * 1024 * 1024

    # 必须的接口
    def getHtml(self, elementid):
        return

    def setHtml(self, html):
        pass

    def navigate(self, url):
        pass

    def add_menu(self, index, label, callback):
        pass

    def add_menu_noselect(self, index, label, callback):
        pass

    #
    def parsehtml(self, html):
        pass

    def set_zoom(self, zoom):
        pass

    def get_zoom(self):
        return 1

    def bind(self, fname, func):
        pass

    def eval(self, js, retsaver=None):
        pass

    def set_transparent_background(self):
        pass

    def _parsehtml_codec(self, html):

        html = """<html><head><meta http-equiv="Content-Type" content="text/html;charset=UTF-8" /></head>{}</html>""".format(
            html
        )
        return html

    def _parsehtml_font(self, html):
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
        html = """<body style=" font-family:'{}'">{}</body>""".format(font, html)
        return html

    def _parsehtml_dark(self, html):
        if nowisdark():
            html = (
                """
    <style>
        body 
        { 
            background-color: rgb(44,44,44);
            color: white; 
        }
    </style>"""
                + html
            )
        return html

    def _parsehtml_dark_auto(self, html):
        return (
            """
<style>
@media (prefers-color-scheme: dark) 
{
    :root {
        color-scheme: dark;
    }
    body 
    { 
        background-color: rgb(44,44,44);
        color: white; 
    }
}
</style>
"""
            + html
        )


class WebviewWidget(abstractwebview):
    html_limit = 1572834
    # https://github.com/MicrosoftEdge/WebView2Feedback/issues/1355#issuecomment-1384161283
    dropfilecallback = pyqtSignal(str)

    def getHtml(self, elementid):
        _ = []
        cb = winsharedutils.html_get_select_text_cb(_.append)
        winsharedutils.get_webview_html(self.get_controller(), cb, elementid)
        if not _:
            return ""
        return json.loads(_[0])

    def __del__(self):
        if not self.webview:
            return
        winsharedutils.remove_ZoomFactorChanged(self.get_controller(), self.__token)
        winsharedutils.remove_WebMessageReceived(
            self.get_controller(), self.m_webMessageReceivedToken
        )
        winsharedutils.remove_ContextMenuRequested(self.get_controller(), self.menudata)

    def bind(self, fname, func):
        self.webview.bind(fname, func)

    def eval(self, js):
        self.webview.eval(js)

    def get_controller(self):
        return self.webview.get_native_handle(
            webview_native_handle_kind_t.WEBVIEW_NATIVE_HANDLE_KIND_BROWSER_CONTROLLER
        )

    def get_hwnd(self):
        return self.webview.get_native_handle(
            webview_native_handle_kind_t.WEBVIEW_NATIVE_HANDLE_KIND_UI_WIDGET
        )

    def add_menu(self, index, label, callback):
        __ = winsharedutils.add_ContextMenuRequested_cb(callback)
        self.callbacks.append(__)
        winsharedutils.add_menu_list(self.menudata, index, label, __)

    def add_menu_noselect(self, index, label, callback):
        __ = winsharedutils.add_ContextMenuRequested_cb2(callback)
        self.callbacks.append(__)
        winsharedutils.add_menu_list_noselect(self.menudata, index, label, __)

    def findFixedRuntime(self):
        isbit64 = platform.architecture()[0] == "64bit"
        maxversion = (0, 0, 0, 0)
        maxvf = None
        for f in os.listdir("."):
            exe = os.path.join(f, "msedgewebview2.exe")
            if not os.path.exists(exe):
                continue
            b = windows.GetBinaryType(exe)
            if (isbit64 and b == 0) or ((not isbit64) and b == 6):
                continue
            version = winsharedutils.queryversion(exe)
            if not version:
                continue
            print(version, f)
            if version > maxversion:
                maxversion = version
                maxvf = os.path.abspath(f)
                print(maxversion, f)
        return maxvf

    @staticmethod
    def showError():
        getQMessageBox(
            gobject.baseobject.commonstylebase,
            "错误",
            "找不到Webview2Runtime！\n请安装Webview2Runtime，或者下载固定版本后解压到软件目录中。",
        )
        os.startfile("https://developer.microsoft.com/microsoft-edge/webview2")

    def __init__(self, parent=None, debug=True) -> None:
        super().__init__(parent)
        self.webview = None
        self.callbacks = []
        FixedRuntime = self.findFixedRuntime()
        if FixedRuntime:
            os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = FixedRuntime
            # 在共享路径上无法运行
            os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--no-sandbox"
        self.webview = Webview(debug=debug, window=int(self.winId()))
        self.m_webMessageReceivedToken = None
        self.menudata = winsharedutils.add_ContextMenuRequested(self.get_controller())
        self.zoomfunc = winsharedutils.add_ZoomFactorChanged_CALLBACK(self.zoomchange)
        self.__token = winsharedutils.add_ZoomFactorChanged(
            self.get_controller(), self.zoomfunc
        )
        self.dropfilecallback__ref = winsharedutils.add_WebMessageReceived_cb(
            self.dropfilecallback.emit
        )
        self.m_webMessageReceivedToken = winsharedutils.add_WebMessageReceived(
            self.get_controller(), self.dropfilecallback__ref
        )
        self.webview.bind("__on_load", self._on_load)
        self.webview.init("""window.__on_load(window.location.href)""")

        self.__darkstate = None
        t = QTimer(self)
        t.setInterval(100)
        t.timeout.connect(self.__darkstatechecker)
        t.timeout.emit()
        t.start()

        self.add_menu(0, "", lambda _: None)
        self.add_menu_noselect(0, "", lambda: None)
        self.cachezoom = 1

    def zoomchange(self, zoom):
        self.cachezoom = zoom
        self.on_ZoomFactorChanged.emit(zoom)
        self.set_zoom(zoom)  # 置为默认值，档navi/sethtml时才能保持

    def __darkstatechecker(self):
        dl = globalconfig["darklight2"]
        if dl == self.__darkstate:
            return
        self.__darkstate = dl
        winsharedutils.put_PreferredColorScheme(self.get_controller(), dl)

    def set_zoom(self, zoom):
        winsharedutils.put_ZoomFactor(self.get_controller(), zoom)
        self.cachezoom = winsharedutils.get_ZoomFactor(self.get_controller())

    def get_zoom(self):
        # winsharedutils.get_ZoomFactor(self.get_controller()) 性能略差
        return self.cachezoom

    def _on_load(self, href):
        self.on_load.emit(href)

    def navigate(self, url):
        self.webview.navigate(url)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        if self.webview:
            hwnd = self.get_hwnd()
            size = a0.size() * self.devicePixelRatioF()
            windows.MoveWindow(hwnd, 0, 0, size.width(), size.height(), True)

    def setHtml(self, html):
        self.webview.set_html(html)

    def set_transparent_background(self):
        winsharedutils.set_transparent_background(self.get_controller())

    def parsehtml(self, html):
        return self._parsehtml_codec(self._parsehtml_dark_auto(html))


class mshtmlWidget(abstractwebview):
    def getHtml(self, elementid):
        _ = []
        cb = winsharedutils.html_get_select_text_cb(_.append)
        winsharedutils.html_get_html(self.browser, cb, elementid)
        if not _:
            return ""
        return _[0]

    def eval(self, js):
        winsharedutils.html_eval(self.browser, js)

    def bindhelper(self, func, ppwc, argc):
        argv = []
        for i in range(argc):
            argv.append(ppwc[argc - 1 - i])
        func(*argv)

    def bind(self, fname, func):
        __f = winsharedutils.html_bind_function_FT(
            functools.partial(self.bindhelper, func)
        )
        self.bindfs.append(__f)
        winsharedutils.html_bind_function(self.browser, fname, __f)

    def __del__(self):
        if not self.browser:
            return
        winsharedutils.html_release(self.browser)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.callbacks = []
        self.bindfs = []
        iswine = checkisusingwine()
        if iswine or (winsharedutils.html_version() < 10001):  # ie10之前，sethtml会乱码
            self.html_limit = 0
        self.browser = winsharedutils.html_new(int(self.winId()))
        self.curr_url = None
        t = QTimer(self)
        t.setInterval(100)
        t.timeout.connect(self.__getcurrent)
        t.timeout.emit()
        t.start()
        self.add_menu(0, _TR("复制"), winsharedutils.clipboard_set)
        self.add_menu(0, None, lambda: 1)

    def __getcurrent(self):
        def __(_u):
            if self.curr_url != _u:
                self.curr_url = _u
                self.on_load.emit(_u)

        cb = winsharedutils.html_get_select_text_cb(__)
        winsharedutils.html_get_current_url(self.browser, cb)

        if winsharedutils.html_check_ctrlc(self.browser):
            cb = winsharedutils.html_get_select_text_cb(winsharedutils.clipboard_set)
            winsharedutils.html_get_select_text(self.browser, cb)

    def navigate(self, url):
        winsharedutils.html_navigate(self.browser, url)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        size = a0.size() * self.devicePixelRatioF()
        winsharedutils.html_resize(self.browser, 0, 0, size.width(), size.height())

    def setHtml(self, html):
        winsharedutils.html_set_html(self.browser, html)

    def parsehtml(self, html):
        return self._parsehtml_codec(self._parsehtml_font(self._parsehtml_dark(html)))

    def add_menu(self, index, label, callback):
        cb = winsharedutils.html_add_menu_cb(callback)
        self.callbacks.append(cb)
        winsharedutils.html_add_menu(self.browser, index, label, cb)

    def add_menu_noselect(self, index, label, callback):
        cb = winsharedutils.html_add_menu_cb2(callback)
        self.callbacks.append(cb)
        winsharedutils.html_add_menu_noselect(self.browser, index, label, cb)


class CustomKeySequenceEdit(QKeySequenceEdit):
    changeedvent = pyqtSignal(str)

    def __init__(self, parent=None):
        super(CustomKeySequenceEdit, self).__init__(parent)

    def keyPressEvent(self, QKeyEvent):
        super(CustomKeySequenceEdit, self).keyPressEvent(QKeyEvent)
        value = self.keySequence()
        if len(value.toString()):
            self.clearFocus()
        self.changeedvent.emit(value.toString().replace("Meta", "Win"))
        self.setKeySequence(QKeySequence(value))


def getsimplekeyseq(dic, key, callback=None):
    key1 = CustomKeySequenceEdit(QKeySequence(dic[key]))

    def __(_d, _k, cb, s):
        _d[_k] = s
        if cb:
            cb()

    key1.changeedvent.connect(functools.partial(__, dic, key, callback))
    return key1


def D_getsimplekeyseq(dic, key, callback=None):
    return lambda: getsimplekeyseq(dic, key, callback)


switchtypes = []


class auto_select_webview(QWidget):
    on_load = pyqtSignal(str)
    on_ZoomFactorChanged = pyqtSignal(float)

    def getHtml(self, elementid):
        return self.internal.getHtml(elementid)

    def eval(self, js):
        self.internal.eval(js)

    def bind(self, funcname, function):
        self.bindinfo.append((funcname, function))
        self.internal.bind(funcname, function)

    def add_menu(self, index, label, callback):
        self.addmenuinfo.append((index, label, callback))
        self.internal.add_menu(index, label, callback)

    def add_menu_noselect(self, index, label, callback):
        self.addmenuinfo_noselect.append((index, label, callback))
        self.internal.add_menu_noselect(index, label, callback)

    def clear(self):
        self.internal.setHtml(self.internal.parsehtml(""))  # 夜间

    def navigate(self, url):
        self.internal.navigate(url)

    def setHtml(self, html):
        html = self.internal.parsehtml(html)
        if len(html) < self.internal.html_limit:
            self.internal.setHtml(html)
        else:
            md5 = hashlib.md5(html.encode("utf8", errors="ignore")).hexdigest()
            lastcachehtml = gobject.gettempdir(md5 + ".html")
            with open(lastcachehtml, "w", encoding="utf8") as ff:
                ff.write(html)
            self.internal.navigate(lastcachehtml)

    def set_zoom(self, zoom):
        self.internal.set_zoom(zoom)

    def sizeHint(self):
        return QSize(256, 192)

    def __init__(self, parent, dyna=False) -> None:
        super().__init__(parent)
        self.addmenuinfo = []
        self.addmenuinfo_noselect = []
        self.bindinfo = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.internal = None
        self.saveurl = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._maybecreate_internal()
        if dyna:
            switchtypes.append(self)
        self.setHtml("")

    @staticmethod
    def switchtype():
        for i, _ in enumerate(switchtypes):
            _._maybecreate_internal(shoudong=True if i == 0 else False)

    def _on_load(self, url: str):
        self.saveurl = url
        self.on_load.emit(url)

    def _createinternal(self, shoudong=False):
        if self.internal:
            self.layout().removeWidget(self.internal)
        self.internal = self._createwebview(shoudong=shoudong)
        self.internal.on_load.connect(self._on_load)
        self.internal.on_ZoomFactorChanged.connect(self.on_ZoomFactorChanged)
        self.layout().addWidget(self.internal)
        for _ in self.addmenuinfo:
            self.internal.add_menu(*_)
        for _ in self.addmenuinfo_noselect:
            self.internal.add_menu_noselect(*_)
        for _ in self.bindinfo:
            self.internal.bind(*_)

    def _maybecreate_internal(self, shoudong=False):
        if not self.internal:
            return self._createinternal(shoudong=shoudong)
        if (
            self.saveurl
            and (self.saveurl != "about:blank")
            and (not self.saveurl.startswith("file:///"))
        ):
            self._createinternal(shoudong=shoudong)
            self.internal.navigate(self.saveurl)
        else:
            html = self.internal.getHtml(None)
            self._createinternal(shoudong=shoudong)
            self.internal.setHtml(html)

    def _createwebview(self, shoudong=False):
        contex = globalconfig["usewebview"]
        if contex == 0:
            browser = mshtmlWidget()
        else:
            try:
                browser = WebviewWidget()
            except:
                print_exc()
                if shoudong:
                    WebviewWidget.showError()
                browser = mshtmlWidget()
                globalconfig["usewebview"] = 0
        return browser


class threebuttons(QWidget):
    btn1clicked = pyqtSignal()
    btn2clicked = pyqtSignal()
    btn3clicked = pyqtSignal()
    btn4clicked = pyqtSignal()
    btn5clicked = pyqtSignal()

    def __init__(self, texts=None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if len(texts) >= 1:
            button = LPushButton(self)
            button.setText(texts[0])
            button.clicked.connect(self.btn1clicked)
            layout.addWidget(button)
        if len(texts) >= 2:
            button2 = LPushButton(self)
            button2.setText(texts[1])
            button2.clicked.connect(self.btn2clicked)

            layout.addWidget(button2)
        if len(texts) >= 3:
            button3 = LPushButton(self)
            button3.setText(texts[2])
            button3.clicked.connect(self.btn3clicked)
            layout.addWidget(button3)
        if len(texts) >= 4:
            button4 = LPushButton(self)
            button4.setText(texts[3])
            button4.clicked.connect(self.btn4clicked)
            layout.addWidget(button4)
        if len(texts) >= 5:
            button5 = LPushButton(self)
            button5.setText(texts[4])
            button5.clicked.connect(self.btn5clicked)
            layout.addWidget(button5)


def tabadd_lazy(tab, title, getrealwidgetfunction):
    q = QWidget()
    v = QVBoxLayout(q)
    v.setContentsMargins(0, 0, 0, 0)
    q.lazyfunction = functools.partial(getrealwidgetfunction, v)
    tab.addTab(q, title)


def makeforms(lay: LFormLayout, lis):
    for line in lis:
        if len(line) == 0:
            lay.addRow(QLabel())
            continue
        elif len(line) == 1:
            name, wid = None, line[0]
        else:
            name, wid = line
        if isinstance(wid, (tuple, list)):
            hb = QHBoxLayout()
            hb.setContentsMargins(0, 0, 0, 0)

            needstretch = False
            for w in wid:
                if callable(w):
                    w = w()
                if w.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed:
                    needstretch = True
                hb.addWidget(w)
            if needstretch:
                hb.insertStretch(0)
                hb.addStretch()
            wid = hb
        else:
            if callable(wid):
                wid = wid()
            elif isinstance(wid, str):
                wid = QLabel(wid)
                wid.setOpenExternalLinks(True)
            if wid.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed:
                hb = QHBoxLayout()
                hb.setContentsMargins(0, 0, 0, 0)
                hb.addStretch()
                hb.addWidget(wid)
                hb.addStretch()
                wid = hb
        if name:
            lay.addRow(name, wid)

        else:
            lay.addRow(wid)


def makegroupingrid(args):
    lis = args.get("grid")
    title = args.get("title", None)
    _type = args.get("type", "form")
    parent = args.get("parent", None)
    groupname = args.get("name", None)
    enable = args.get("enable", True)
    internallayoutname = args.get("internallayoutname", None)
    group = LGroupBox()
    if not enable:
        group.setEnabled(False)
    if groupname and parent:
        setattr(parent, groupname, group)
    if title:
        group.setTitle(title)
    else:
        group.setObjectName("notitle")

    if _type == "grid":
        grid = QGridLayout(group)
        automakegrid(grid, lis)
        if internallayoutname:
            setattr(parent, internallayoutname, grid)
    elif _type == "form":
        lay = LFormLayout(group)
        makeforms(lay, lis)
        if internallayoutname:
            setattr(parent, internallayoutname, lay)
    return group


def automakegrid(grid: QGridLayout, lis, save=False, savelist=None):

    maxl = 0
    linecolss = []
    for nowr, line in enumerate(lis):
        nowc = 0
        linecolssx = []
        for item in line:
            if type(item) == str:
                cols = 1
            elif type(item) != tuple:
                wid, cols = item, 1
            elif len(item) == 2:

                wid, cols = item
            elif len(item) == 3:
                wid, cols, arg = item
            nowc += cols
            linecolssx.append(cols)
        maxl = max(maxl, nowc)
        linecolss.append(linecolssx)

    for nowr, line in enumerate(lis):
        nowc = 0
        if save:
            ll = []
        for item in line:
            if type(item) == str:
                cols = 1
                wid = LLabel(item)
            elif type(item) != tuple:
                wid, cols = item, 1
            elif len(item) == 2:

                wid, cols = item
                if type(wid) == str:
                    wid = LLabel(wid)
            elif len(item) == 3:
                wid, cols, arg = item
                if type(wid) == str:
                    wid = QLabel(wid)
                    if arg == "link":
                        wid.setOpenExternalLinks(True)
                elif arg == "group":
                    wid = makegroupingrid(wid)
            if cols > 0:
                cols = cols
            elif cols == 0:
                cols = maxl - sum(linecolss[nowr])
            else:
                cols = -maxl // cols
            do = None
            if callable(wid):
                wid = wid()
                if isinstance(wid, tuple):
                    wid, do = wid
            grid.addWidget(wid, nowr, nowc, 1, cols)
            if do:
                do()
            if save:
                ll.append(wid)
            nowc += cols
        if save:
            savelist.append(ll)
        grid.setRowMinimumHeight(nowr, 25)


def makegrid(grid=None, save=False, savelist=None, savelay=None, delay=False):

    class gridwidget(QWidget):
        pass

    gridlayoutwidget = gridwidget()
    gridlay = QGridLayout(gridlayoutwidget)
    gridlay.setAlignment(Qt.AlignmentFlag.AlignTop)
    gridlayoutwidget.setStyleSheet("gridwidget{background-color:transparent;}")

    def do(gridlay, grid, save, savelist, savelay):
        automakegrid(gridlay, grid, save, savelist)
        if save:
            savelay.append(gridlay)

    __do = functools.partial(do, gridlay, grid, save, savelist, savelay)

    if not delay:
        __do()
        return gridlayoutwidget
    return gridlayoutwidget, __do


def makescroll():
    scroll = QScrollArea()
    # scroll.setHorizontalScrollBarPolicy(1)
    scroll.setStyleSheet("""QScrollArea{background-color:transparent;border:0px}""")
    scroll.setWidgetResizable(True)
    return scroll


def makescrollgrid(grid, lay, save=False, savelist=None, savelay=None):
    wid, do = makegrid(grid, save, savelist, savelay, delay=True)
    swid = makescroll()
    lay.addWidget(swid)
    swid.setWidget(wid)
    do()
    return wid


def makesubtab_lazy(
    titles=None, functions=None, klass=None, callback=None, delay=False, initial=None
):
    if klass:
        tab: LTabWidget = klass()
    else:
        tab = LTabWidget()

    def __(t: LTabWidget, initial, i):
        if initial:
            object, key = initial
            object[key] = i
        try:
            w = t.currentWidget()
            if "lazyfunction" in dir(w):
                w.lazyfunction()
                delattr(w, "lazyfunction")
        except:
            print_exc()
        if callback:
            callback(i)

    can = initial and (initial[1] in initial[0])
    if not can:
        tab.currentChanged.connect(functools.partial(__, tab, initial))

    def __do(tab: LTabWidget, titles, functions, initial):
        if titles and functions:
            for i, func in enumerate(functions):
                tabadd_lazy(tab, titles[i], func)
        if can:
            tab.setCurrentIndex(initial[0][initial[1]])
            tab.currentChanged.connect(functools.partial(__, tab, initial))
            tab.currentChanged.emit(initial[0][initial[1]])

    ___do = functools.partial(__do, tab, titles, functions, initial)
    if not delay:
        ___do()
        return tab
    else:
        return tab, ___do


@Singleton_close
class listediter(LDialog):
    def showmenu(self, p: QPoint):
        curr = self.hctable.currentIndex()
        if not curr.isValid():
            return
        menu = QMenu(self.hctable)
        remove = LAction("删除")
        copy = LAction("复制")
        up = LAction("上移")
        down = LAction("下移")
        if not (self.isrankeditor):
            menu.addAction(remove)
            menu.addAction(copy)
        if not (self.candidates):
            menu.addAction(up)
            menu.addAction(down)
        action = menu.exec(self.hctable.cursor().pos())

        if action == remove:
            self.hcmodel.removeRow(curr.row())
            self.internalrealname.pop(curr.row())
        elif action == copy:
            winsharedutils.clipboard_set(self.hcmodel.itemFromIndex(curr).text())

        elif action == up:

            self.moverank(-1)

        elif action == down:
            self.moverank(1)

    def moverank(self, dy):
        _pair = self.hctable.moverank(dy)
        if not _pair:
            return
        src, tgt = _pair
        self.internalrealname.insert(tgt, self.internalrealname.pop(src))

    def __init__(
        self,
        parent,
        title,
        lst,
        closecallback=None,
        ispathsedit=None,
        isrankeditor=False,
        namemapfunction=None,
        candidates=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.lst = lst
        self.candidates = candidates
        self.closecallback = closecallback
        self.ispathsedit = ispathsedit
        self.isrankeditor = isrankeditor
        try:
            self.setWindowTitle(title)
            model = LStandardItemModel()
            self.hcmodel = model
            self.namemapfunction = namemapfunction
            table = TableViewW()
            table.horizontalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            if isrankeditor or (not (ispathsedit is None)) or self.candidates:
                table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode((QAbstractItemView.SelectionMode.SingleSelection))
            table.setWordWrap(False)
            table.setModel(model)

            table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            table.customContextMenuRequested.connect(self.showmenu)
            self.hctable = table
            self.internalrealname = []
            formLayout = QVBoxLayout(self)
            formLayout.addWidget(self.hctable)
            for row, k in enumerate(lst):  # 2
                try:
                    if namemapfunction:
                        namemapfunction(k)
                except:
                    continue
                self.internalrealname.append(k)
                if namemapfunction:
                    k = namemapfunction(k)
                item = QStandardItem(k)
                self.hcmodel.insertRow(row, [item])

                if candidates:
                    combo = SuperCombo()
                    _vis = self.candidates
                    if self.namemapfunction:
                        _vis = [self.namemapfunction(_) for _ in _vis]
                    combo.addItems(_vis)
                    combo.setCurrentIndex(self.candidates.index(lst[row]))
                    combo.currentIndexChanged.connect(
                        functools.partial(self.__changed, item)
                    )
                    self.hctable.setIndexWidget(self.hcmodel.index(row, 0), combo)
            if isrankeditor:
                self.buttons = threebuttons(texts=["上移", "下移"])
                self.buttons.btn1clicked.connect(functools.partial(self.moverank, -1))
                self.buttons.btn2clicked.connect(functools.partial(self.moverank, 1))
            elif self.candidates:
                self.buttons = threebuttons(texts=["添加行", "删除行"])
                self.buttons.btn1clicked.connect(self.click1)
                self.buttons.btn2clicked.connect(self.clicked2)
            else:
                if self.ispathsedit and self.ispathsedit.get("dirorfile", False):
                    self.buttons = threebuttons(
                        texts=["添加文件", "添加文件夹", "删除行", "上移", "下移"]
                    )
                    self.buttons.btn1clicked.connect(
                        functools.partial(self._addfile, False)
                    )
                    self.buttons.btn2clicked.connect(
                        functools.partial(self._addfile, True)
                    )
                    self.buttons.btn3clicked.connect(self.clicked2)
                    self.buttons.btn4clicked.connect(
                        functools.partial(self.moverank, -1)
                    )
                    self.buttons.btn5clicked.connect(
                        functools.partial(self.moverank, 1)
                    )
                else:
                    xx = "添加行"
                    if self.ispathsedit:
                        if self.ispathsedit.get("isdir", False):
                            xx = "添加文件夹"
                        else:
                            xx = "添加文件"
                    self.buttons = threebuttons(texts=[xx, "删除行", "上移", "下移"])
                    self.buttons.btn1clicked.connect(self.click1)
                    self.buttons.btn2clicked.connect(self.clicked2)
                    self.buttons.btn3clicked.connect(
                        functools.partial(self.moverank, -1)
                    )
                    self.buttons.btn4clicked.connect(
                        functools.partial(self.moverank, 1)
                    )

            formLayout.addWidget(self.buttons)
            self.resize(600, self.sizeHint().height())
            self.show()
        except:
            print_exc()

    def clicked2(self):
        skip = self.hctable.removeselectedrows()
        for row in skip:
            self.internalrealname.pop(row)

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.buttons.setFocus()

        rows = self.hcmodel.rowCount()
        rowoffset = 0
        dedump = set()
        if self.closecallback:
            before = pickle.dumps(self.lst)
        self.lst.clear()
        for row in range(rows):
            if self.namemapfunction:
                k = self.internalrealname[row]
            else:
                k = self.hcmodel.item(row, 0).text()
            if k == "" or k in dedump:
                rowoffset += 1
                continue
            self.lst.append(k)
            dedump.add(k)
        if self.closecallback:
            after = pickle.dumps(self.lst)
            self.closecallback(before != after)

    def __cb(self, paths):
        if isinstance(paths, str):
            paths = [paths]
        for path in paths:
            self.internalrealname.insert(0, path)
            self.hcmodel.insertRow(0, [QStandardItem(path)])

    def __changed(self, item: QStandardItem, idx):
        self.internalrealname[item.row()] = self.candidates[idx]

    def _addfile(self, isdir):
        openfiledirectory(
            "",
            multi=True,
            edit=None,
            isdir=isdir,
            filter1=self.ispathsedit.get("filter1", "*.*"),
            callback=self.__cb,
        )

    def click1(self):
        if self.candidates:
            self.internalrealname.insert(0, self.candidates[0])
            item = QStandardItem("")
            self.hcmodel.insertRow(0, [item])
            combo = SuperCombo()
            _vis = self.candidates
            if self.namemapfunction:
                _vis = [self.namemapfunction(_) for _ in _vis]
            combo.addItems(_vis)
            combo.currentIndexChanged.connect(functools.partial(self.__changed, item))
            self.hctable.setIndexWidget(self.hcmodel.index(0, 0), combo)
        elif self.ispathsedit is None:
            self.internalrealname.insert(0, "")
            self.hcmodel.insertRow(0, [QStandardItem("")])
        else:
            openfiledirectory(
                "",
                multi=True,
                edit=None,
                isdir=self.ispathsedit.get("isdir", False),
                filter1=self.ispathsedit.get("filter1", "*.*"),
                callback=self.__cb,
            )


class ClickableLine(QLineEdit):
    clicked = pyqtSignal()

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


class listediterline(QWidget):

    def text(self):
        return self.edit.text()

    def setText(self, t):
        return self.edit.setText(t)

    def __init__(
        self,
        name,
        reflist,
        ispathsedit=None,
        directedit=False,
        specialklass=None,
    ):
        super().__init__()
        self.edit = ClickableLine()
        self.reflist = reflist
        self.setText("|".join((str(_) for _ in reflist)))
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.edit)
        if not specialklass:
            specialklass = listediter
        callback = functools.partial(
            specialklass,
            self,
            name,
            reflist,
            closecallback=self.callback,
            ispathsedit=ispathsedit,
        )
        self.directedit = directedit
        if directedit:

            def __(t):
                self.reflist.clear()
                self.reflist.extend(t.split("|"))

            self.edit.textChanged.connect(__)

            def __2():
                self.edit.setReadOnly(True)
                callback()

            hbox.addWidget(getIconButton(icon="fa.gear", callback=__2))
        else:
            self.edit.setReadOnly(True)
            self.edit.clicked.connect(callback)

    def callback(self, changed):
        if changed:
            self.setText("|".join((str(_) for _ in self.reflist)))
        if self.directedit:
            self.edit.setReadOnly(False)


def openfiledirectory(directory, multi, edit, isdir, filter1="*.*", callback=None):
    if isdir:
        res = QFileDialog.getExistingDirectory(directory=directory)
    else:
        res = (QFileDialog.getOpenFileName, QFileDialog.getOpenFileNames)[multi](
            directory=directory, filter=filter1
        )[0]

    if not res:
        return
    if isinstance(res, list):
        res = [os.path.normpath(_) for _ in res]
    else:
        res = os.path.normpath(res)
    if edit:
        edit.setText("|".join(res) if isinstance(res, list) else res)
    if callback:
        callback(res)


def getsimplepatheditor(
    text=None,
    multi=False,
    isdir=False,
    filter1="*.*",
    callback=None,
    icons=None,
    reflist=None,
    name=None,
    header=None,
    dirorfile=False,
    clearable=True,
    clearset=None,
    isfontselector=False,
):
    lay = QHBoxLayout()
    lay.setContentsMargins(0, 0, 0, 0)
    if multi:
        e = listediterline(
            name,
            reflist,
            dict(isdir=isdir, multi=False, filter1=filter1, dirorfile=dirorfile),
        )
        lay.addWidget(e)
    else:
        e = QLineEdit(text)
        e.setReadOnly(True)
        if icons:
            bu = getIconButton(icon=icons[0])
            if clearable:
                clear = getIconButton(icon=icons[1])
        else:
            bu = LPushButton("选择" + ("文件夹" if isdir else "文件"))
            if clearable:
                clear = LPushButton("清除")
        if clearable:
            lay.clear = clear

        if isfontselector:

            def __selectfont(callback, e):
                f = QFont()
                text = e.text()
                if text:
                    f.fromString(text)
                font, ok = QFontDialog.getFont(f, e)
                if ok:
                    _s = font.toString()
                    callback(_s)
                    e.setText(_s)

            _cb = functools.partial(__selectfont, callback, e)
        else:
            _cb = functools.partial(
                openfiledirectory,
                text,
                multi,
                e,
                isdir,
                "" if isdir else filter1,
                callback,
            )
        bu.clicked.connect(_cb)
        lay.addWidget(e)
        lay.addWidget(bu)
        if clearable:

            def __(_cb, _e, t):
                _cb("")
                if not t:
                    _e.setText("")
                elif callable(t):
                    _e.setText(t())

            clear.clicked.connect(functools.partial(__, callback, e, clearset))
            lay.addWidget(clear)
    return lay


class pixmapviewer(QWidget):
    tolastnext = pyqtSignal(int)

    def wheelEvent(self, e: QWheelEvent) -> None:
        self.tolastnext.emit([-1, 1][e.angleDelta().y() < 0])
        return super().wheelEvent(e)

    def __init__(self, p=None) -> None:
        super().__init__(p)
        self.pix = None
        self._pix = None
        self.boxtext = [], []

    def showpixmap(self, pix: QPixmap):
        pix.setDevicePixelRatio(self.devicePixelRatioF())
        self.pix = pix
        self._pix = None
        self.boxtext = [], []
        self.update()

    def showboxtext(self, box, text):
        self._pix = None
        self.boxtext = box, text
        self.update()

    def paintEvent(self, e):
        if self.pix:
            if self._pix:
                if self._pix.size() != self.size() * self.devicePixelRatioF():
                    self._pix = None
            if not self._pix:

                rate = self.devicePixelRatioF()
                self._pix = QPixmap(self.size() * rate)
                self._pix.setDevicePixelRatio(rate)
                self._pix.fill(Qt.GlobalColor.transparent)

                if not self.pix.isNull():
                    painter = QPainter(self._pix)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    pix = self.pix.scaled(
                        self.size() * self.devicePixelRatioF(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    x = self.width() / 2 - pix.width() / 2 / self.devicePixelRatioF()
                    y = self.height() / 2 - pix.height() / 2 / self.devicePixelRatioF()
                    painter.drawPixmap(int(x), int(y), pix)
                    boxs, texts = self.boxtext
                    try:
                        scale = pix.height() / self.pix.height() / rate
                        parsex = lambda xx: (xx) * scale + x
                        parsey = lambda yy: (yy) * scale + y
                        font = QFont()
                        font.setFamily(globalconfig["fonttype"])
                        font.setPointSizeF(globalconfig["fontsizeori"])
                        pen = QPen()
                        pen.setColor(QColor(globalconfig["rawtextcolor"]))
                        painter.setFont(font)
                        painter.setPen(pen)
                        for i in range(len(boxs)):
                            painter.drawText(
                                QPointF(parsex(boxs[i][0]), parsey(boxs[i][1])),
                                texts[i],
                            )
                            for j in range(len(boxs[i]) // 2):
                                painter.drawLine(
                                    QPointF(
                                        parsex(boxs[i][j * 2]),
                                        parsey(boxs[i][j * 2 + 1]),
                                    ),
                                    QPointF(
                                        parsex(boxs[i][(j * 2 + 2) % len(boxs[i])]),
                                        parsey(boxs[i][(j * 2 + 3) % len(boxs[i])]),
                                    ),
                                )
                    except:
                        print_exc()
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self._pix)
        return super().paintEvent(e)


class IconButton(QPushButton):
    clicked_1 = pyqtSignal()

    def event(self, e):
        if e.type() == QEvent.Type.FontChange:
            h = QFontMetricsF(self.font()).height()
            h = int(h * gobject.Consts.btnscale)
            sz = QSize(h, h)
            self.setFixedSize(sz)
            self.setIconSize(sz)
        elif e.type() == QEvent.Type.EnabledChange:
            self.seticon()
        return super().event(e)

    def __init__(self, icon, enable=True, qicon=None, parent=None, checkable=False):
        super().__init__(parent)
        self._icon = icon
        self.clicked.connect(self.clicked_1)
        self.clicked.connect(self.seticon)
        self._qicon = qicon
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border:transparent;padding: 0px;")
        self.setCheckable(checkable)
        self.setEnabled(enable)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def seticon(self):
        if self._qicon:
            icon = self._qicon
        else:
            if self.isCheckable():
                if isinstance(self._icon, str):
                    icons = [self._icon, self._icon]
                else:
                    icons = self._icon
                icon = icons[self.isChecked()]
                colors = ["", gobject.Consts.buttoncolor]
                color = QColor(colors[self.isChecked()])
            else:
                color = QColor(gobject.Consts.buttoncolor)
                icon = self._icon
            if not self.isEnabled():
                color = disablecolor(color)
            icon = qtawesome.icon(icon, color=color)
        self.setIcon(icon)

    def setChecked(self, a0):
        super().setChecked(a0)
        self.seticon()

    def setEnabled(self, _):
        super().setEnabled(_)
        self.seticon()


class SplitLine(QFrame):
    def __init__(self, *argc):
        super().__init__(*argc)
        self.setStyleSheet("background-color: gray;")
        self.setFixedHeight(2)


def clearlayout(ll: QLayout):
    while ll.count():
        item = ll.takeAt(0)
        if not item:
            continue
        w = item.widget()
        if w:
            w.hide()
            w.deleteLater()
            continue
        l = item.layout()
        if l:
            clearlayout(l)
            l.deleteLater()
            continue


def showhidelayout(ll: QLayout, vis):
    for _ in range(ll.count()):
        item = ll.itemAt(_)
        if not item:
            continue
        w = item.widget()
        if w:
            if vis:
                if not w.isVisible():
                    w.setVisible(True)
            else:
                w.setVisible(False)
            continue
        l = item.layout()
        if l:
            showhidelayout(l, vis)
            continue


class FQPlainTextEdit(QPlainTextEdit):
    def mousePressEvent(self, a0: QMouseEvent) -> None:
        # 点击浏览器后，无法重新获取焦点。
        windows.SetFocus(int(self.winId()))
        return super().mousePressEvent(a0)


class FQLineEdit(QLineEdit):
    def mousePressEvent(self, a0: QMouseEvent) -> None:
        # 点击浏览器后，无法重新获取焦点。
        windows.SetFocus(int(self.winId()))
        return super().mousePressEvent(a0)


class VisLFormLayout(LFormLayout):
    # 简易实现
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._row_widgets = {}
        self._reverse = {}
        self._row_vis = {}

    def addRow(self, label_or_field, field=None):
        row_index = self.rowCount()
        if field is None:
            super().addRow(label_or_field)
            field = label_or_field
            label_or_field = None
        else:
            super().addRow(label_or_field, field)
        self._row_widgets[row_index] = (label_or_field, field)
        self._row_vis[row_index] = True
        self._reverse[field] = row_index
        return row_index

    def setRowVisible(self, row_index, visible):
        if isinstance(row_index, int):
            pass
        elif isinstance(row_index, (QWidget, QLayout)):
            row_index = self._reverse[row_index]
        if self._row_vis[row_index] == visible:
            return
        insert_position = sum(1 for i in range(row_index) if self._row_vis[i])
        if visible:
            label, field = self._row_widgets[row_index]
            if label is not None:
                super().insertRow(insert_position, label, field)
            else:
                super().insertRow(insert_position, field)
            if isinstance(field, QWidget):
                if not field.isVisible():
                    field.setVisible(True)
            else:
                showhidelayout(field, True)
        else:
            tres = self.takeRow(insert_position)
            label = tres.labelItem
            if label is not None:
                self.removeItem(label)
                label.widget().deleteLater()
            if tres.fieldItem.widget():
                tres.fieldItem.widget().hide()
            else:
                showhidelayout(tres.fieldItem.layout(), False)
        self._row_vis[row_index] = visible


class CollapsibleBox(QGroupBox):
    def __init__(self, delayloadfunction=None, parent=None, margin0=True):
        super(CollapsibleBox, self).__init__(parent)
        self.setObjectName("notitle")
        lay = QVBoxLayout(self)
        if margin0:
            lay.setContentsMargins(0, 0, 0, 0)
        self.func = delayloadfunction
        self.toggle(False)

    def toggle(self, checked):
        if checked and self.func:
            self.func(self.layout())
            self.func = None
        self.setVisible(checked)


class CollapsibleBoxWithButton(QWidget):

    def __init__(self, delayloadfunction=None, title="", parent=None):
        super(CollapsibleBoxWithButton, self).__init__(parent)
        self.toggle_button = LToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_button.toggled.connect(self.toggled)
        self.content_area = CollapsibleBox(delayloadfunction, self)
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)
        self.toggled(False)

    def toggled(self, checked):
        self.toggle_button.setChecked(checked)
        self.content_area.toggle(checked)
        self.toggle_button.setIcon(
            qtawesome.icon("fa.chevron-down" if checked else "fa.chevron-right")
        )


class editswitchTextBrowser(QWidget):
    textChanged = pyqtSignal(str)

    def heightForWidth(self, w):
        return self.browser.heightForWidth(w)

    def resizeEvent(self, a0):
        self.switch.move(self.width() - self.switch.width(), 0)
        return super().resizeEvent(a0)

    def __init__(self, parent=None):
        super().__init__(parent)
        stack = QStackedWidget()
        self.edit = QPlainTextEdit()
        self.browser = QLabel()
        self.browser.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.browser.setWordWrap(True)
        self.browser.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.edit.textChanged.connect(
            lambda: (
                self.browser.setText(
                    "<html>"
                    + re.sub(
                        r'href="([^"]+)"',
                        "",
                        re.sub(r'src="([^"]+)"', "", self.edit.toPlainText()),
                    )
                    + "</html>"
                ),
                self.textChanged.emit(self.edit.toPlainText()),
            )
        )
        stack.addWidget(self.browser)
        stack.addWidget(self.edit)
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(stack)
        self.switch = IconButton(parent=self, icon="fa.edit", checkable=True)
        self.switch.setFixedSize(QSize(25, 25))
        self.switch.raise_()
        self.switch.clicked.connect(stack.setCurrentIndex)

    def settext(self, text):
        self.edit.setPlainText(text)

    def text(self):
        return self.edit.toPlainText()


class FlowWidget(QWidget):
    def __init__(self, parent=None, groups=3):
        super().__init__(parent)
        self.margin = QMargins(5, 5, 5, 5)
        self.spacing = 5
        self._item_list = [[] for _ in range(groups)]

    def insertWidget(self, group, index, w: QWidget):
        w.setParent(self)
        w.show()
        self._item_list[group].insert(index, w)
        self.doresize()

    def addWidget(self, group, w: QWidget):
        self.insertWidget(group, len(self._item_list[group]), w)

    def removeWidget(self, w: QWidget):
        for _ in self._item_list:
            if w in _:
                _.remove(w)
                w.deleteLater()
                self.doresize()
                break

    def doresize(self):
        line_height = 0
        spacing = self.spacing
        y = self.margin.left()
        for listi in self._item_list:
            x = self.margin.top()
            for i, item in enumerate(listi):

                next_x = x + item.sizeHint().width() + spacing
                if (
                    next_x - spacing + self.margin.right() > self.width()
                    and line_height > 0
                ):
                    x = self.margin.top()
                    y = y + line_height + spacing
                    next_x = x + item.sizeHint().width() + spacing

                size = item.sizeHint()
                if (i == len(listi) - 1) and isinstance(item, editswitchTextBrowser):
                    w = self.width() - self.margin.right() - x
                    size = QSize(w, max(size.height(), item.heightForWidth(w)))

                item.setGeometry(QRect(QPoint(x, y), size))
                line_height = max(line_height, size.height())
                x = next_x
            y = y + line_height + spacing
        self.setFixedHeight(y + self.margin.bottom() - spacing)

    def resizeEvent(self, a0):
        self.doresize()
