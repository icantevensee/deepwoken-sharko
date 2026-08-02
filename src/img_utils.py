"""
Utilities for image manipulation, including text rendering and format conversion.
"""
import numpy as np

from PyQt6.QtGui import QImage, QPixmap, QPainter, QFont, QFontMetricsF, QTransform
from PyQt6.QtCore import Qt


class ImgUtils:

    def _render_text_image(self, text, size):
        """Render long multiline text into an RGBA QImage with precise layout fitting and zero RAM leakage."""

        width, height = size
        img = QImage(width, height, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)

        painter = QPainter()
        if not painter.begin(img):
            return img

        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

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
                get_width = getattr(metrics, "horizontalAdvance", metrics.horizontalAdvance)

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
        result.fill(Qt.GlobalColor.transparent)

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
        result.fill(Qt.GlobalColor.transparent)
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
        qimg = qimg.convertToFormat(QImage.Format.Format_ARGB32)
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

    @staticmethod
    def numpy_blur_rgba(alpha_channel, radius=7, passes=3):
        """Box blur approximation of a Gaussian blur with numpy vectorized shifting."""
        blur = alpha_channel.astype(np.float32)
        kernel_size = 2 * radius + 1

        def _box_1d(arr, axis):
            padded = np.pad(arr, [(radius + 1, radius) if a == axis else (0, 0)
                                  for a in range(arr.ndim)], mode="edge")
            cumulative = np.cumsum(padded, axis=axis)
            upper = np.take(cumulative, np.arange(kernel_size, cumulative.shape[axis]), axis=axis)
            lower = np.take(cumulative, np.arange(0, cumulative.shape[axis] - kernel_size), axis=axis)
            return (upper - lower) / kernel_size

        for _ in range(passes):
            blur = _box_1d(blur, 1)
            blur = _box_1d(blur, 0)

        return np.clip(blur, 0, 255).astype(np.uint8)

    @staticmethod
    def draw_blurred_semicircle_window(input_pixmap, inner_radius, swing_angle):
        """Render a blurred semicircle window from a source pixmap, returns: tuple[QPixmap, float]: result and downscale factor"""
        temp_img = input_pixmap.transformed(QTransform().rotate(90)).toImage()

        temp_img = temp_img.convertToFormat(QImage.Format.Format_RGBA8888)

        width, height = temp_img.width(), temp_img.height()
        ptr = temp_img.bits()
        ptr.setsize(height * width * 4)
        custom_img_arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))

        orig_h, orig_w = custom_img_arr.shape[:2]

        # Clamp canvas bounds
        rect_h = min(300, orig_h)
        rect_w = int(orig_w * (rect_h / float(orig_h)))

        # Scale image with step metrics
        y_indices = np.linspace(0, orig_h - 1, rect_h).astype(np.int32)
        x_indices = np.linspace(0, orig_w - 1, rect_w).astype(np.int32)
        src_rgba = custom_img_arr[np.ix_(y_indices, x_indices)].astype(np.float32)

        smear_scale = orig_h / float(rect_h)
        inner_radius = int(inner_radius / smear_scale)

        outer_radius = inner_radius + rect_h
        size = int(outer_radius * 2.2)

        # Vectorized coordinate mesh grids
        X_grid, Y_grid = np.meshgrid(np.arange(size), np.arange(size))
        center_x = size * 0.5
        center_y = size * 0.5

        # Continuous negative angle mapping boundaries
        start_angle_deg = 270.0 - swing_angle
        end_angle_deg = -90.0 + swing_angle

        start_angle_rad = np.radians(start_angle_deg)
        end_angle_rad = np.radians(end_angle_deg)
        total_arc_span = start_angle_rad - end_angle_rad

        dx = X_grid - center_x
        dy = Y_grid - center_y
        radius = np.sqrt(dx**2 + dy**2)

        # Calculate raw polar rotation angles
        angle = np.arctan2(dy, dx)

        # Shift the angles to allow negative angles
        angle_shifted = (angle - end_angle_rad) % (2 * np.pi) + end_angle_rad

        # Geometric boundary limits
        in_radius = (radius >= inner_radius) & (radius <= outer_radius)
        in_angle = (angle_shifted >= end_angle_rad) & (angle_shifted <= start_angle_rad)
        arc_pixels_mask = in_radius & in_angle

        linear_angular_pct = np.clip((start_angle_rad - angle_shifted) / total_arc_span, 0.0, 1.0)
        radial_pct = np.clip((radius - inner_radius) / float(rect_h), 0.0, 1.0)

        # Linear mapping layout
        float_x = linear_angular_pct * (rect_w - 1)
        float_y = radial_pct * (rect_h - 1)

        # Extract subpixel coordinates for native pixel blending
        x0 = np.floor(float_x).astype(np.int32)
        x1 = np.minimum(x0 + 1, rect_w - 1)
        y0 = np.floor(float_y).astype(np.int32)
        y1 = np.minimum(y0 + 1, rect_h - 1)

        wa = (x1 - float_x) * (y1 - float_y)
        wb = (float_x - x0) * (y1 - float_y)
        wc = (x1 - float_x) * (float_y - y0)
        wd = (float_x - x0) * (float_y - y0)

        # Apply geometric tapering near the tail
        head_protection_zone = 0.05
        is_in_tail = linear_angular_pct > head_protection_zone
        tail_pct = np.clip((linear_angular_pct - head_protection_zone) / (1.0 - head_protection_zone), 0.0, 1.0)

        taper_factor = 0.3 + 0.7 * (1.0 - tail_pct)
        half_h = rect_h / 2.0
        dist_from_center = np.abs((radial_pct * rect_h) - half_h)

        taper_pass = np.where(is_in_tail, dist_from_center <= (half_h * taper_factor), True)
        final_valid_mask = arc_pixels_mask & taper_pass

        # Initialize color array buffer
        warped_rgba = np.zeros((size, size, 4), dtype=np.float32)

        # Bilinear rendering calculation loop
        for c in range(4):
            warped_rgba[final_valid_mask, c] = (
                wa[final_valid_mask] * src_rgba[y0[final_valid_mask], x0[final_valid_mask], c] +
                wb[final_valid_mask] * src_rgba[y0[final_valid_mask], x1[final_valid_mask], c] +
                wc[final_valid_mask] * src_rgba[y1[final_valid_mask], x0[final_valid_mask], c] +
                wd[final_valid_mask] * src_rgba[y1[final_valid_mask], x1[final_valid_mask], c]
            )

        # Non linear smooth falloff on alpha
        alpha_mask = np.zeros((size, size), dtype=np.float32)

        # Using a power curve factor for smooth trail off
        alpha_decay = 1.0 - np.power(tail_pct, 0.6)
        alpha_mask[final_valid_mask] = np.where(is_in_tail[final_valid_mask], alpha_decay[final_valid_mask] * 255.0, 255.0)

        # Blend transparency values into float color array matrix
        warped_rgba[:, :, 3] = np.clip(warped_rgba[:, :, 3] * (alpha_mask / 255.0), 0.0, 255.0)

        # Smooth boundary transition edges using the native rolling pass blur
        blur_radius = max(3, int(size * 0.01))
        alpha_channel = warped_rgba[:, :, 3].astype(np.uint8)
        blurred_alpha = ImgUtils.numpy_blur_rgba(alpha_channel, radius=blur_radius, passes=3)
        warped_rgba[:, :, 3] = blurred_alpha.astype(np.float32)

        # Wipe color channels outside the mask area to prevent artifacts
        for c in range(3):
            warped_rgba[:, :, c] = np.where(arc_pixels_mask, warped_rgba[:, :, c], 0.0)

        # Turn into usable qpixmap
        visual_output = np.zeros((size, size, 4), dtype=np.uint8)
        alpha_channel = np.clip(warped_rgba[:, :, 3], 0, 255).astype(np.uint8)
        for c in range(3):
            visual_output[:, :, c] = np.clip(warped_rgba[:, :, c], 0, 255).astype(np.uint8)
        visual_output[:, :, 3] = alpha_channel

        img_rgba = visual_output
        height, width, channel = img_rgba.shape
        bytes_per_line = channel * width

        q_image = QImage(img_rgba.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)

        return QPixmap.fromImage(q_image), smear_scale

    @staticmethod
    def draw_solid_semicircle_window(input_pixmap, inner_radius, swing_angle):
        """Render a solid semicircle window from a source pixmap, returns: tuple[QPixmap, float]: result and downscale factor"""
        temp_img = input_pixmap.transformed(QTransform().rotate(90)).toImage()
        temp_img = temp_img.convertToFormat(QImage.Format.Format_RGBA8888)
        width, height = temp_img.width(), temp_img.height()
        ptr = temp_img.bits()
        ptr.setsize(height * width * 4)
        custom_img_arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))

        orig_h, orig_w = custom_img_arr.shape[:2]
        rect_h = min(300, orig_h)
        rect_w = int(orig_w * (rect_h / float(orig_h)))

        y_indices = np.linspace(0, orig_h - 1, rect_h).astype(np.int32)
        x_indices = np.linspace(0, orig_w - 1, rect_w).astype(np.int32)
        src_rgba = custom_img_arr[np.ix_(y_indices, x_indices)].astype(np.float32)

        scale = orig_h / float(rect_h)
        inner_radius = int(inner_radius / scale)

        outer_radius = inner_radius + rect_h
        size = int(outer_radius * 2.2)

        X_grid, Y_grid = np.meshgrid(np.arange(size), np.arange(size))
        center_x, center_y = size * 0.5, size * 0.5

        start_angle_deg, end_angle_deg = 270.0 - swing_angle, -90.0 + swing_angle
        start_angle_rad = np.radians(start_angle_deg)
        end_angle_rad = np.radians(end_angle_deg)
        total_arc_span = start_angle_rad - end_angle_rad

        dx, dy = X_grid - center_x, Y_grid - center_y
        radius = np.sqrt(dx**2 + dy**2)
        angle = np.arctan2(dy, dx)
        angle_shifted = (angle - end_angle_rad) % (2 * np.pi) + end_angle_rad

        in_radius = (radius >= inner_radius) & (radius <= outer_radius)
        in_angle = (angle_shifted >= end_angle_rad) & (angle_shifted <= start_angle_rad)
        arc_pixels_mask = in_radius & in_angle

        angular_pct = np.clip((start_angle_rad - angle_shifted) / total_arc_span, 0.0, 1.0)
        radial_pct = np.clip((radius - inner_radius) / float(rect_h), 0.0, 1.0)

        # Uniform mapping and seamless alignment.
        float_x = angular_pct * (rect_w - 1)
        float_y = radial_pct * (rect_h - 1)

        x0 = np.floor(float_x).astype(np.int32)
        x1 = np.minimum(x0 + 1, rect_w - 1)
        y0 = np.floor(float_y).astype(np.int32)
        y1 = np.minimum(y0 + 1, rect_h - 1)

        wa = (x1 - float_x) * (y1 - float_y)
        wb = (float_x - x0) * (y1 - float_y)
        wc = (x1 - float_x) * (float_y - y0)
        wd = (float_x - x0) * (float_y - y0)

        warped_rgba = np.zeros((size, size, 4), dtype=np.float32)
        for c in range(4):
            warped_rgba[arc_pixels_mask, c] = (
                wa[arc_pixels_mask] * src_rgba[y0[arc_pixels_mask], x0[arc_pixels_mask], c] +
                wb[arc_pixels_mask] * src_rgba[y0[arc_pixels_mask], x1[arc_pixels_mask], c] +
                wc[arc_pixels_mask] * src_rgba[y1[arc_pixels_mask], x0[arc_pixels_mask], c] +
                wd[arc_pixels_mask] * src_rgba[y1[arc_pixels_mask], x1[arc_pixels_mask], c]
            )

        alpha_mask = np.zeros((size, size), dtype=np.float32)
        alpha_mask[arc_pixels_mask] = 255.0
        warped_rgba[:, :, 3] = alpha_mask

        for c in range(3):
            warped_rgba[:, :, c] = np.where(arc_pixels_mask, warped_rgba[:, :, c], 0.0)

        visual_output = np.zeros((size, size, 4), dtype=np.uint8)
        alpha_channel = np.clip(warped_rgba[:, :, 3], 0, 255).astype(np.uint8)
        for c in range(3):
            visual_output[:, :, c] = np.clip(warped_rgba[:, :, c], 0, 255).astype(np.uint8)
        visual_output[:, :, 3] = alpha_channel

        img_rgba = visual_output
        height, width, channel = img_rgba.shape
        bytes_per_line = channel * width

        q_image = QImage(img_rgba.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(q_image), scale
