"""
Utilities for image manipulation, including text rendering and format conversion.
"""
import numpy as np

from PyQt5.QtGui import QImage, QPixmap, QPainter, QFont, QFontMetricsF
from PyQt5.QtCore import Qt


class ImgUtils:

    def _render_text_image(self, text, size):
        """Render long multiline text into an RGBA QImage with precise layout fitting and zero RAM leakage."""

        width, height = size
        img = QImage(width, height, QImage.Format_ARGB32)
        img.fill(Qt.transparent)

        painter = QPainter()
        if not painter.begin(img):
            return img

        try:
            painter.setRenderHint(QPainter.TextAntialiasing, True)

            font = QFont(self.SPEECH_FONT_FAMILY)
            padding = self.TEXT_RENDER_PADDING
            line_spacing = self.TEXT_LINE_SPACING
            allowable_w = width - padding * 2
            allowable_h = height - padding * 2

            best_font_size = None
            best_lines = []

            low = float(self.FONT_SIZE_MIN)
            high = float(self.FONT_SIZE_MAX)
            tolerance = 0.1
            words = text.split()

            while (high - low) > tolerance:
                mid = (low + high) / 2.0
                font.setPointSizeF(mid)

                metrics = QFontMetricsF(font)
                get_width = getattr(metrics, "horizontalAdvance", metrics.width)

                lines = []
                cur = ""
                fit_failed = False

                for w in words:
                    if get_width(w) > allowable_w:
                        fit_failed = True
                        break

                    test = (cur + " " + w).strip()
                    if get_width(test) <= allowable_w:
                        cur = test
                    else:
                        if cur:
                            lines.append(cur)
                        cur = w
                if cur:
                    lines.append(cur)

                single_line_h = metrics.height()
                total_h = (len(lines) * single_line_h) + ((len(lines) - 1) * line_spacing) if lines else 0

                if total_h <= allowable_h and not fit_failed:
                    best_font_size = mid
                    best_lines = lines
                    low = mid
                else:
                    high = mid

            if best_font_size and best_lines:
                font.setPointSizeF(best_font_size)
                painter.setFont(font)
                metrics = QFontMetricsF(font)
                single_line_h = metrics.height()

                y_cursor = padding + metrics.ascent()
                for line in best_lines:
                    painter.drawText(int(padding), int(y_cursor), line)
                    y_cursor += single_line_h + line_spacing

        finally:
            painter.end()

        return img

    def composite_on_base(self, base_pixmap, text_image):
        """Composite a text QImage onto a base QPixmap at the speech box position."""
        result = QPixmap(base_pixmap.size())
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.drawPixmap(0, 0, base_pixmap)

        if self.current_facing == "Left":
            x = self.TEXT_OFFSET_LEFT
        else:
            x = self.TEXT_OFFSET_RIGHT
        y = self.QUESTION_BOX_TOP_Y

        painter.drawImage(x, y, text_image)
        painter.end()
        return result

    def composite_three(self, base_pixmap, q_img, opt1_img, opt2_img):
        """Composites three Qimages onto a base pixmap for question and answers."""
        result = QPixmap(base_pixmap.size())
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.drawPixmap(0, 0, base_pixmap)
        x = self.TEXT_OFFSET_LEFT if self.current_facing == "Left" else self.TEXT_OFFSET_RIGHT
        painter.drawImage(x, self.QUESTION_BOX_TOP_Y, q_img)
        painter.drawImage(x, self.QUESTION_BOX_OPTION1_Y, opt1_img)
        painter.drawImage(x, self.QUESTION_BOX_OPTION2_Y, opt2_img)
        painter.end()
        return result

    @staticmethod
    def tint_pixmap(pixmap, color):
        """Apply a color tint to a pixmap using multiplicative and masking composition modes."""
        painter = QPainter(pixmap)
        original = QPixmap(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.fillRect(pixmap.rect(), color)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawPixmap(0, 0, original)
        painter.end()

    @staticmethod
    def _remove_black_background_qimg(qimg):
        """Remove near black background pixels from a qimage by manipulating its argb data as a numpy array."""
        qimg = qimg.convertToFormat(QImage.Format_ARGB32)
        h, w = qimg.height(), qimg.width()

        ptr = qimg.bits()
        ptr.setsize(h * w * 4)

        arr_32 = np.frombuffer(ptr, dtype=np.uint32)

        blue  =  arr_32        & 0xFF
        green = (arr_32 >> 8)  & 0xFF
        red   = (arr_32 >> 16) & 0xFF

        black_mask = (red <= 15) & (green <= 15) & (blue <= 15)

        arr_32 &= 0x00FFFFFF
        arr_32 |= np.where(black_mask, 0x00000000, 0xFF000000).astype(np.uint32)
        return qimg
