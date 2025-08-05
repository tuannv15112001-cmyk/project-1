import sys
import os
import cv2
import json
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QRubberBand, QLabel
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PyQt5.QtGui import QImage, QPixmap
from test2 import Ui_MainWindow  # file UI bạn đã cung cấp

class MyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_hsv_threshold = {
            'lower': [0, 0, 0],
            'upper': [180, 255, 255]
        }
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.image = None
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.roi_width = 100
        self.roi_height = 100
        self.current_band = None
        self.roi_offset = QPoint()
        self.dragging = False
        self.drawing_roi = False
        self.deletion_mode = False
        self.saved_rois = {}

        # Kết nối nút
        self.ui.capture_button.clicked.connect(self.capture_image)
        self.ui.load_button.clicked.connect(self.load_image)
        self.ui.load_button_2.clicked.connect(self.save_image)
        self.ui.drawroi_button.clicked.connect(self.start_draw_roi)
        self.ui.set_roi.clicked.connect(self.set_roi_size)
        self.ui.delete_button.clicked.connect(self.activate_deletion)
        self.ui.setcolor_black.clicked.connect(lambda: self.save_hsv_threshold('black'))
        self.ui.setcolor_blue.clicked.connect(lambda: self.save_hsv_threshold('blue'))
        self.ui.setcolor_white.clicked.connect(lambda: self.save_hsv_threshold('white'))

        self.load_saved_hsv_thresholds()

        for i in range(2, 6):
            getattr(self.ui, f"saveHSV_layer{i}").clicked.connect(
                lambda _, i=i: self.save_layer_pixel_threshold_min(i))  # Lưu giá trị pixel vào Min
        self.ui.save_layer.clicked.connect(self.save_all_layer_pixel_thresholds)

            # Load lại khi khởi động:
        self.load_layer_pixel_labels()

        for i in range(1, 7):
            getattr(self.ui, f"save_pos{i}").clicked.connect(lambda _, i=i: self.save_roi(f"pos{i}"))

        # Gán sự kiện chuột
        self.ui.ROI_Screen.mousePressEvent = self.roi_mouse_press
        self.ui.ROI_Screen.mouseMoveEvent = self.roi_mouse_move
        self.ui.ROI_Screen.mouseReleaseEvent = self.roi_mouse_release

        self.load_rois_from_file()
        self.setup_hsv_slider_connections()
        self.load_saved_hsv_thresholds()
        self.load_layer_pixel_labels()

    def set_roi_size(self):
        try:
            self.roi_width = int(self.ui.Width_roi.toPlainText())
            self.roi_height = int(self.ui.Length_roi.toPlainText())
            print(f"Đã thiết lập ROI size: {self.roi_width} x {self.roi_height}")
        except:
            print("Lỗi: nhập số nguyên cho Width/Length")

    def start_draw_roi(self):
        self.drawing_roi = True

        if self.current_band:
            self.current_band.hide()

        self.current_band = QLabel(self.ui.ROI_Screen)
        self.current_band.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0);
            border: 2px solid red;
        """)
        self.current_band.setAlignment(Qt.AlignCenter)
        self.current_band.setText("NEW")

        center = self.ui.ROI_Screen.rect().center()
        top_left = QPoint(center.x() - self.roi_width // 2, center.y() - self.roi_height // 2)
        roi_rect = QRect(top_left, QSize(self.roi_width, self.roi_height))

        self.current_band.setGeometry(roi_rect)
        self.current_band.show()
        self.roi_offset = QPoint()

    def roi_mouse_press(self, event):
        if self.current_band and self.current_band.geometry().contains(event.pos()):
            self.roi_offset = event.pos() - self.current_band.geometry().topLeft()
            self.dragging = True

    def roi_mouse_move(self, event):
        if self.dragging and self.current_band:
            new_top_left = event.pos() - self.roi_offset
            roi_rect = QRect(new_top_left, QSize(self.roi_width, self.roi_height))
            roi_rect = roi_rect.intersected(self.ui.ROI_Screen.rect())
            self.current_band.setGeometry(roi_rect)

    def roi_mouse_release(self, event):
        self.dragging = False

    def capture_image(self):
        ret, frame = self.cap.read()
        if ret:
            self.image = frame
            self.display_image(frame)
            self.redraw_saved_rois()
            self.update_pixel_counts()
            self.update_all_pos_labels()
            self.check_layer_match()

    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            image = cv2.imread(file_path)
            self.image = image
            self.display_image(image)
            self.redraw_saved_rois()
            self.update_all_pos_labels()
            self.update_pixel_counts()
            self.check_layer_match()


    def save_image(self):
        if self.image is None:
            print("Chưa có ảnh để lưu.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Lưu ảnh", "", "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)")
        if file_path:
            cv2.imwrite(file_path, self.image)
            print("Đã lưu ảnh:", file_path)

    def display_image(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        qt_pixmap = QPixmap.fromImage(qt_image)
        self.ui.ROI_Screen.setPixmap(qt_pixmap.scaled(
            self.ui.ROI_Screen.width(),
            self.ui.ROI_Screen.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        ))

    def update_roi_preview(self, pos_name):
        if pos_name not in self.saved_rois or self.ui.ROI_Screen.pixmap() is None:
            return

        label = getattr(self.ui, f"{pos_name}_label")  # Ví dụ: self.ui.pos1_label
        roi = self.saved_rois[pos_name].geometry()
        full_pixmap = self.ui.ROI_Screen.pixmap()

        # Cắt vùng ảnh theo ROI
        cropped = full_pixmap.copy(roi)
        label.setPixmap(cropped.scaled(label.width(), label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def save_roi(self, pos_name):
        if self.deletion_mode:
            if pos_name in self.saved_rois:
                self.saved_rois[pos_name].hide()
                del self.saved_rois[pos_name]
                self.save_rois_to_file()
                print(f"Đã xóa ROI tại {pos_name}")
            self.deletion_mode = False
            return

        if self.current_band:
            if pos_name in self.saved_rois:
                self.saved_rois[pos_name].hide()

            # Đổi màu viền và ghi tên ROI
            self.current_band.setStyleSheet("""
                background-color: rgba(0, 0, 0, 0);
                border: 2px solid green;
            """)
            self.current_band.setText(pos_name.upper())
            self.current_band.setAlignment(Qt.AlignCenter)
            self.saved_rois[pos_name] = self.current_band

            self.save_rois_to_file()
            print(f"Đã lưu ROI {pos_name}")
            self.current_band = None
            self.update_roi_preview(pos_name)



    def setup_hsv_slider_connections(self):
        self.ui.SliderLH.setMinimum(0)
        self.ui.SliderLH.setMaximum(180)
        self.ui.SliderUH.setMinimum(0)
        self.ui.SliderUH.setMaximum(180)

        self.ui.SliderLS.setMinimum(0)
        self.ui.SliderLS.setMaximum(255)
        self.ui.SliderUS.setMinimum(0)
        self.ui.SliderUS.setMaximum(255)

        self.ui.SliderLV.setMinimum(0)
        self.ui.SliderLV.setMaximum(255)
        self.ui.SliderUV.setMinimum(0)
        self.ui.SliderUV.setMaximum(255)

        self.ui.SliderLH.valueChanged.connect(self.update_hsv_threshold)
        self.ui.SliderUH.valueChanged.connect(self.update_hsv_threshold)
        self.ui.SliderLS.valueChanged.connect(self.update_hsv_threshold)
        self.ui.SliderUS.valueChanged.connect(self.update_hsv_threshold)
        self.ui.SliderLV.valueChanged.connect(self.update_hsv_threshold)
        self.ui.SliderUV.valueChanged.connect(self.update_hsv_threshold)

    def update_hsv_threshold(self):
        lh = self.ui.SliderLH.value()
        uh = self.ui.SliderUH.value()
        ls = self.ui.SliderLS.value()
        us = self.ui.SliderUS.value()
        lv = self.ui.SliderLV.value()
        uv = self.ui.SliderUV.value()

        self.ui.lower_H.setText(str(lh))
        self.ui.uper_H.setText(str(uh))
        self.ui.lower_S.setText(str(ls))
        self.ui.uper_S.setText(str(us))
        self.ui.lower_V.setText(str(lv))
        self.ui.uper_V.setText(str(uv))

        self.current_hsv_threshold['lower'] = [lh, ls, lv]
        self.current_hsv_threshold['upper'] = [uh, us, uv]
        self.update_all_pos_labels()
        self.update_all_pos_labels()
        self.update_pixel_counts()

    def update_all_pos_labels(self):


        for pos_name in self.saved_rois.keys():
            self.update_roi_preview(pos_name)
            self.update_roi_hsv_preview(pos_name)



    def update_roi_hsv_preview(self, pos_name):
        if pos_name not in self.saved_rois or self.ui.ROI_Screen.pixmap() is None:
            return

        label_name = f"{pos_name}_label"
        screen_name = f"{pos_name}_screen"

        if not hasattr(self.ui, label_name) or not hasattr(self.ui, screen_name):
            return

        roi = self.saved_rois[pos_name].geometry()
        full_pixmap = self.ui.ROI_Screen.pixmap()
        cropped_pixmap = full_pixmap.copy(roi)

        cropped_qimg = cropped_pixmap.toImage().convertToFormat(QImage.Format_RGB888)
        width, height = cropped_qimg.width(), cropped_qimg.height()
        ptr = cropped_qimg.bits()
        ptr.setsize(cropped_qimg.byteCount())

        import numpy as np
        arr = np.array(ptr).reshape((height, width, 3))
        bgr_img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
        lower = tuple(self.current_hsv_threshold['lower'])
        upper = tuple(self.current_hsv_threshold['upper'])
        mask = cv2.inRange(hsv, lower, upper)
        # Làm mịn và xói mòn
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        result = cv2.bitwise_and(bgr_img, bgr_img, mask=mask)
        result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        qimg_result = QImage(result_rgb.data, result_rgb.shape[1], result_rgb.shape[0], result_rgb.strides[0], QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg_result)

        getattr(self.ui, screen_name).setPixmap(pix.scaled(
            getattr(self.ui, screen_name).size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def activate_deletion(self):
        self.deletion_mode = True
        print("Đang ở chế độ xóa. Ấn save_posX để xóa ROI tương ứng.")

    def save_rois_to_file(self):
        data = {}
        for pos_name, label in self.saved_rois.items():
            rect = label.geometry()
            data[pos_name] = {
                "x": rect.x(),
                "y": rect.y(),
                "w": rect.width(),
                "h": rect.height()
            }
        with open("saved_rois.json", "w") as f:
            json.dump(data, f)
        print("Đã lưu ROI vào file.")

    def load_rois_from_file(self):
        if not os.path.exists("saved_rois.json"):
            return
        with open("saved_rois.json", "r") as f:
            data = json.load(f)
        for pos_name, val in data.items():
            rect = QRect(val["x"], val["y"], val["w"], val["h"])
            label = QLabel(self.ui.ROI_Screen)
            label.setGeometry(rect)
            label.setStyleSheet("border: 2px solid green; background-color: rgba(0,0,0,0);")
            label.setText(pos_name.upper())
            label.setAlignment(Qt.AlignCenter)
            label.show()
            self.saved_rois[pos_name] = label

    def redraw_saved_rois(self):
        for band in self.saved_rois.values():
            band.setParent(self.ui.ROI_Screen)
            band.show()

    def save_hsv_threshold(self, color_name):

        lower = self.current_hsv_threshold['lower']
        upper = self.current_hsv_threshold['upper']

        file_path = "color_hsv_values.json"
        data = {}
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)

        data[color_name] = {
            "min": lower,
            "max": upper
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

        print(f"Đã lưu HSV cho màu {color_name}: min={lower}, max={upper}")

        self.update_all_pos_labels()
        self.update_pixel_counts()

    def load_saved_hsv_thresholds(self):
        file_path = "color_hsv_values.json"
        if not os.path.exists(file_path):
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        # Ví dụ: load HSV của màu "black" mặc định đầu tiên
        if "black" in data:
            min_vals = data["black"]["min"]
            max_vals = data["black"]["max"]

            self.ui.SliderLH.setValue(min_vals[0])
            self.ui.SliderLS.setValue(min_vals[1])
            self.ui.SliderLV.setValue(min_vals[2])

            self.ui.SliderUH.setValue(max_vals[0])
            self.ui.SliderUS.setValue(max_vals[1])
            self.ui.SliderUV.setValue(max_vals[2])

            print("Đã load HSV mặc định cho màu black")



    def count_pixels_from_labels(self, color_name):
        file_path = "color_hsv_values.json"
        if not os.path.exists(file_path):
            return 0

        with open(file_path, "r") as f:
            data = json.load(f)

        if color_name not in data:
            return 0

        min_hsv = np.array(data[color_name]["min"], dtype=np.uint8)
        max_hsv = np.array(data[color_name]["max"], dtype=np.uint8)

        total_count = 0

        for i in range(1, 7):  # pos1 to pos6
            label_name = f"pos{i}_label"
            if not hasattr(self.ui, label_name):
                continue

            label = getattr(self.ui, label_name)
            pixmap = label.pixmap()
            if pixmap is None or pixmap.isNull():
                continue

            qimg = pixmap.toImage()
            if qimg.isNull():
                continue

            qimg = qimg.convertToFormat(QImage.Format_RGB888)
            w, h = qimg.width(), qimg.height()

            try:
                ptr = qimg.bits()
                ptr.setsize(qimg.byteCount())
                stride = qimg.bytesPerLine()
                buf = np.frombuffer(ptr, dtype=np.uint8).reshape((h, stride))  # still 2D
                img = buf[:, :w * 3].reshape((h, w, 3))  # now valid (h, w, 3)

            except Exception as e:
                print(f"[Lỗi chuyển đổi ảnh]: {e}")
                continue

            bgr_img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, min_hsv, max_hsv)
            total_count += cv2.countNonZero(mask)

        return total_count

    def update_pixel_counts(self):
        black_pixels = self.count_pixels_from_labels("black")
        blue_pixels = self.count_pixels_from_labels("blue")
        white_pixels = self.count_pixels_from_labels("white")

        self.ui.value_black.setText(str(black_pixels))
        self.ui.value_blue.setText(str(blue_pixels))
        self.ui.value_white.setText(str(white_pixels))

        self.ui.result_black.setText(str(black_pixels))
        self.ui.result_blue.setText(str(blue_pixels))
        self.ui.result_white.setText(str(white_pixels))

        print(f"[Pixel Count] Black: {black_pixels}, Blue: {blue_pixels}, White: {white_pixels}")

    def save_layer_pixel_to_file(self, layer_num, min_vals, max_vals):
        file_path = "layer_pixel_thresholds.json"
        data = {}
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)

        layer_key = f"layer{layer_num}"
        data[layer_key] = {
            "min": min_vals,
            "max": max_vals
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

        print(f"Đã lưu {layer_key} min={min_vals}, max={max_vals}")

    def save_layer_pixel_threshold_min(self, layer_num):
        try:
            black = int(self.ui.value_black.text())
            blue = int(self.ui.value_blue.text())
            white = int(self.ui.value_white.text())
        except:
            print("Lỗi: không đọc được value_*")
            return

        getattr(self.ui, f"layer{layer_num}_setMinBlack").setText(str(black))
        getattr(self.ui, f"layer{layer_num}_setMinBlue").setText(str(blue))
        getattr(self.ui, f"layer{layer_num}_setMinWhite").setText(str(white))

    def save_all_layer_pixel_thresholds(self):
        for i in range(2, 6):
            self.save_layer_pixel_threshold_manual(i)

    def save_layer_pixel_threshold_manual(self, layer_num):
        try:
            min_black = int(getattr(self.ui, f"layer{layer_num}_setMinBlack").text())
            min_blue = int(getattr(self.ui, f"layer{layer_num}_setMinBlue").text())
            min_white = int(getattr(self.ui, f"layer{layer_num}_setMinWhite").text())
            max_black = int(getattr(self.ui, f"layer{layer_num}_setMaxBlack").text())
            max_blue = int(getattr(self.ui, f"layer{layer_num}_setMaxBlue").text())
            max_white = int(getattr(self.ui, f"layer{layer_num}_setMaxWhite").text())
        except:
            print("Lỗi: không đọc được QLineEdit")
            return

        self.save_layer_pixel_to_file(layer_num,
                                      {"black": min_black, "blue": min_blue, "white": min_white},
                                      {"black": max_black, "blue": max_blue, "white": max_white})

    def check_layer_match(self):
        try:
            result_black = int(self.ui.result_black.text())
            result_blue = int(self.ui.result_blue.text())
            result_white = int(self.ui.result_white.text())
        except:
            print("Lỗi: không đọc được result_*")
            return

        for i in range(2, 6):
            layer_key = f"layer{i}"
            label_name = f"{layer_key}_label"

            if not hasattr(self.ui, label_name):
                continue

            label = getattr(self.ui, label_name)
            label.setStyleSheet("")  # reset màu

            try:
                min_black = int(getattr(self.ui, f"{layer_key}_setMinBlack").text())
                min_blue = int(getattr(self.ui, f"{layer_key}_setMinBlue").text())
                min_white = int(getattr(self.ui, f"{layer_key}_setMinWhite").text())
                max_black = int(getattr(self.ui, f"{layer_key}_setMaxBlack").text())
                max_blue = int(getattr(self.ui, f"{layer_key}_setMaxBlue").text())
                max_white = int(getattr(self.ui, f"{layer_key}_setMaxWhite").text())
            except:
                continue

            def in_range(val, min_val, max_val):
                margin_min = int(min_val * 0.1)
                margin_max = int(max_val * 0.1)
                return (min_val - margin_min <= val <= max_val + margin_max)

            if (
                in_range(result_black, min_black, max_black) and
                in_range(result_blue, min_blue, max_blue) and
                in_range(result_white, min_white, max_white)
            ):
                label.setStyleSheet("background-color: rgb(85, 255, 0);")


    # === Trong __init__() ===
    # Kết nối các nút:

    def load_layer_pixel_labels(self):
        file_path = "layer_pixel_thresholds.json"
        if not os.path.exists(file_path):
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        for i in range(2, 6):
            layer_key = f"layer{i}"
            if layer_key not in data:
                continue
            try:
                getattr(self.ui, f"{layer_key}_setMinBlack").setText(str(data[layer_key]["min"]["black"]))
                getattr(self.ui, f"{layer_key}_setMinBlue").setText(str(data[layer_key]["min"]["blue"]))
                getattr(self.ui, f"{layer_key}_setMinWhite").setText(str(data[layer_key]["min"]["white"]))
                getattr(self.ui, f"{layer_key}_setMaxBlack").setText(str(data[layer_key]["max"]["black"]))
                getattr(self.ui, f"{layer_key}_setMaxBlue").setText(str(data[layer_key]["max"]["blue"]))
                getattr(self.ui, f"{layer_key}_setMaxWhite").setText(str(data[layer_key]["max"]["white"]))
            except Exception as e:
                print(f"[Lỗi gán QLineEdit]: {layer_key} - {e}")


    def closeEvent(self, event):
        if self.cap.isOpened():
            self.cap.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyMainWindow()
    window.show()
    sys.exit(app.exec_())
