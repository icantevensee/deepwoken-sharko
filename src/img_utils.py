"""
Utilities for image manipulation, including text rendering and format conversion.
"""

from PIL import         Image, ImageDraw, ImageFont
from PyQt5.QtGui import QImage, QPixmap


class ImgUtils:
    def _render_text_image(self, text, size):
        img = Image.new("RGBA", (size[0], size[1]), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        base_font_path = self.FONT
        padding = self.TEXT_RENDER_PADDING
        line_spacing = self.TEXT_LINE_SPACING

        for font_size in range(self.FONT_SIZE_MAX, self.FONT_SIZE_MIN, -1):
            font = ImageFont.truetype(base_font_path, font_size)

            words = text.split()
            lines = []
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                bbox = draw.multiline_textbbox((0, 0), test, font=font)
                tw = bbox[2] - bbox[0]
                if tw <= size[0] - padding * 2:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)

            allowable_w = size[0] - padding * 2
            too_wide = False
            for l in lines:
                try:
                    bbox = draw.multiline_textbbox((0, 0), l, font=font)
                    if bbox[2] - bbox[0] > allowable_w:
                        too_wide = True
                        break
                except Exception:
                    too_wide = True
                    break
            if too_wide:
                continue

            try:
                ascent, descent = font.getmetrics()
                single_line_h = ascent + descent
            except Exception:
                try:
                    bbox = draw.textbbox((0, 0), "Mg", font=font)
                    single_line_h = bbox[3] - bbox[1]
                except Exception:
                    single_line_h = 12
            total_h = single_line_h * len(lines) + (len(lines) - 1) * line_spacing
            if total_h <= size[1] - padding * 2:
                y = 0
                for i, l in enumerate(lines):
                    bbox = draw.multiline_textbbox((0, 0), l, font=font)
                    tw = bbox[2] - bbox[0]
                    x = 0
                    draw.text((x, y), l, font=font, fill=(0, 0, 0, 255))
                    y += single_line_h + line_spacing
                return img

        draw.text((0, 0), text, font=ImageFont.load_default(), fill=(0, 0, 0, 255))
        return img

    @staticmethod
    def _pil_to_qpixmap(pil_image):
        """Convert PIL Image to QPixmap."""
        if isinstance(pil_image, QPixmap):
            return pil_image

        pil_image_rgb = pil_image.convert("RGBA")
        data = pil_image_rgb.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_image_rgb.width, pil_image_rgb.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    @staticmethod
    def _flip_photoimage(pil_image):
        """Flip PIL image horizontally."""
        try:
            if isinstance(pil_image, Image.Image):
                return pil_image.transpose(Image.FLIP_LEFT_RIGHT)
            return pil_image
        except Exception as e:
            print(f"Error flipping image: {e}")
            return pil_image

    @staticmethod
    def _flip_image(pil_image):
        """Flip PIL image horizontally and convert to QImage."""
        flipped = pil_image.transpose(Image.FLIP_LEFT_RIGHT)
        if flipped.mode == "RGBA":
            data = flipped.tobytes("raw", "RGBA")
            return QImage(data, flipped.width, flipped.height, QImage.Format_RGBA8888)
        else:
            data = flipped.tobytes("raw", "RGB")
            return QImage(data, flipped.width, flipped.height, QImage.Format_RGB888)

    def composite_on_base(self, base_img, text_img):
        b = base_img.copy()
        if self.current_facing == "Left":
            x = self.TEXT_OFFSET_LEFT
        else:
            x = self.TEXT_OFFSET_RIGHT
        y = self.QUESTION_BOX_TOP_Y
        b.paste(text_img, (x, y), text_img)
        return b
