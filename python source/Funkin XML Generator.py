import io
import os
import sys
import math
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pygame


def safe_font(size=16, bold=False):
    for name in ("segoeui", "arial", "dejavusans", "liberationsans"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size)


def trim_surface(surf):
    rect = surf.get_bounding_rect(min_alpha=1)
    if rect.width == 0 or rect.height == 0:
        return surf, 0, 0, surf.get_width(), surf.get_height()
    trimmed = surf.subsurface(rect).copy()
    return trimmed, -rect.x, -rect.y, surf.get_width(), surf.get_height()


def build_sparrow_xml(image_path, entries):
    root = ET.Element("TextureAtlas")
    root.set("imagePath", os.path.basename(image_path))

    for e in entries:
        sub = ET.SubElement(root, "SubTexture")
        sub.set("name", e["name"])
        sub.set("x", str(e["x"]))
        sub.set("y", str(e["y"]))
        sub.set("width", str(e["w"]))
        sub.set("height", str(e["h"]))
        if e.get("frame_w") is not None:
            sub.set("frameX", str(e["frame_x"]))
            sub.set("frameY", str(e["frame_y"]))
            sub.set("frameWidth", str(e["frame_w"]))
            sub.set("frameHeight", str(e["frame_h"]))

    raw = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(raw)
    pretty = parsed.toprettyxml(indent="    ")
    lines = [ln for ln in pretty.splitlines() if ln.strip()]
    if lines and lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    lines.insert(1, "<!--  Created With Funkin XML Generator  -->")
    return "\n".join(lines)


def pack_simple(images):
    if not images:
        return pygame.Surface((1, 1), pygame.SRCALPHA), []

    order = sorted(
        range(len(images)),
        key=lambda i: images[i][1].get_height(),
        reverse=True
    )

    total_area = sum(s.get_width() * s.get_height() for _, s in images)
    target_w = max(
        max(s.get_width() for _, s in images),
        int(math.sqrt(total_area) * 1.2)
    )
    target_w = min(target_w, 2048)

    positions = [None] * len(images)
    x = y = 0
    shelf_h = 0
    atlas_w = 0

    for idx in order:
        surf = images[idx][1]
        w, h = surf.get_size()
        if x + w > target_w and x > 0:
            x = 0
            y += shelf_h
            shelf_h = 0
        positions[idx] = (x, y)
        x += w
        shelf_h = max(shelf_h, h)
        atlas_w = max(atlas_w, x)

    atlas_h = y + shelf_h
    atlas = pygame.Surface((max(atlas_w, 1), max(atlas_h, 1)), pygame.SRCALPHA)

    entries = []
    for i, (name, surf) in enumerate(images):
        px, py = positions[i]
        atlas.blit(surf, (px, py))
        entries.append({
            "name": name,
            "x": px,
            "y": py,
            "w": surf.get_width(),
            "h": surf.get_height()
        })

    return atlas, entries


def save_zip(zip_path, atlas_surface, xml_str, png_name="atlas.png"):
    tmp = io.BytesIO()
    pygame.image.save(atlas_surface, tmp, "atlas.png")
    png_data = tmp.getvalue()
    xml_name = os.path.splitext(png_name)[0] + ".xml"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(png_name, png_data)
        zf.writestr(xml_name, xml_str.encode("utf-8"))


def dialog_open_files():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        paths = filedialog.askopenfilenames(
            title="Выбери кадры (PNG)",
            filetypes=[("PNG", "*.png"), ("All", "*.*")]
        )
        root.destroy()
        return list(paths)
    except Exception as e:
        print("dialog_open_files error:", e)
        return []


def dialog_choose_dir(initial=None):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(
            title="Куда сохранить ZIP",
            initialdir=initial if initial and os.path.isdir(initial) else None
        )
        root.destroy()
        return path or ""
    except Exception as e:
        print("dialog_choose_dir error:", e)
        return ""


class FunkinXMLGenerator:
    C_BG      = (30, 30, 30)
    C_PANEL   = (45, 45, 45)
    C_INPUT   = (25, 25, 25)
    C_GREEN   = (0, 220, 120)
    C_RED     = (220, 50, 50)
    C_WHITE   = (230, 230, 230)
    C_GREY    = (90, 90, 90)
    C_DARK    = (15, 15, 15)
    C_ACCENT  = (60, 180, 255)
    C_BLUE    = (80, 140, 220)

    BTN_W   = 240
    RIGHT_W = 340

    def __init__(self):
        pygame.init()
        self.W, self.H = 1280, 720
        self.screen = pygame.display.set_mode((self.W, self.H), pygame.RESIZABLE)
        pygame.display.set_caption("Funkin XML Generator")

        self.clock  = pygame.time.Clock()
        self.font   = safe_font(18)
        self.font_s = safe_font(14)
        self.font_b = safe_font(20, bold=True)
        self.font_B = safe_font(28, bold=True)

        self.frames   = []
        self.selected = -1
        self.scroll   = 0

        self.name_text    = "atlas"
        self.path_text    = os.path.abspath("output")
        self.active_field = None
        self.do_trim      = True

        self.message = "Готово. Добавь кадры через 'ДОБАВИТЬ КАДР'."
        self.running = True

    def add_frames(self):
        paths = dialog_open_files()
        if not paths:
            d = "frames"
            if os.path.isdir(d):
                paths = [
                    os.path.join(d, f)
                    for f in sorted(os.listdir(d))
                    if f.lower().endswith(".png")
                ]

        added = 0
        for p in paths:
            try:
                s = pygame.image.load(p).convert_alpha()
                self.frames.append({"name": os.path.basename(p), "surface": s})
                added += 1
            except Exception as e:
                print("Load fail:", p, e)

        if added:
            self.selected = len(self.frames) - 1
            self.message = f"Добавлено кадров: {added}"
        elif not paths:
            self.message = "Файлы не выбраны."

    def delete_selected(self):
        if 0 <= self.selected < len(self.frames):
            self.frames.pop(self.selected)
            if self.frames:
                self.selected = min(self.selected, len(self.frames) - 1)
            else:
                self.selected = -1
            self.message = "Кадр удалён"

    def browse_output(self):
        d = dialog_choose_dir(self.path_text)
        if d:
            self.path_text = d
            self.message = f"Папка: {d}"

    def do_save(self):
        if not self.frames:
            self.message = "Нет кадров для сохранения!"
            return

        name = (self.name_text or "atlas").strip() or "atlas"
        out_dir = (self.path_text or ".").strip()

        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            self.message = f"Ошибка пути: {e}"
            return

        prepared = []
        for f in self.frames:
            base_name = os.path.splitext(f["name"])[0]
            if self.do_trim:
                trimmed, fx, fy, ow, oh = trim_surface(f["surface"])
                prepared.append((base_name + ".png", trimmed, (fx, fy, ow, oh)))
            else:
                prepared.append((base_name + ".png", f["surface"], None))

        try:
            atlas, entries = pack_simple([(n, s) for n, s, _ in prepared])
        except Exception as e:
            self.message = f"Ошибка упаковки: {e}"
            return

        for e, (_, _, fd) in zip(entries, prepared):
            if fd is not None:
                e["frame_x"], e["frame_y"], e["frame_w"], e["frame_h"] = fd

        png_name = f"{name}.png"
        xml_str = build_sparrow_xml(png_name, entries)

        zip_path = os.path.join(out_dir, f"{name}.zip")
        try:
            save_zip(zip_path, atlas, xml_str, png_name=png_name)
            self.message = f"Сохранено: {zip_path}"
        except Exception as e:
            self.message = f"Ошибка ZIP: {e}"

    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
            return

        if ev.type == pygame.VIDEORESIZE:
            self.W, self.H = ev.w, ev.h
            self.screen = pygame.display.set_mode(
                (self.W, self.H), pygame.RESIZABLE
            )
            return

        if ev.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if mx < self.BTN_W:
                self.scroll -= ev.y * 40
                self._clamp_scroll()

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self._on_click(ev.pos)

        if ev.type == pygame.KEYDOWN:
            if self.active_field == "name":
                if ev.key == pygame.K_BACKSPACE:
                    self.name_text = self.name_text[:-1]
                elif ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    self.active_field = None
                elif ev.unicode and ev.unicode.isprintable():
                    self.name_text += ev.unicode
            elif self.active_field == "path":
                if ev.key == pygame.K_BACKSPACE:
                    self.path_text = self.path_text[:-1]
                elif ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    self.active_field = None
                elif ev.unicode and ev.unicode.isprintable():
                    self.path_text += ev.unicode
            else:
                if ev.key == pygame.K_DELETE:
                    self.delete_selected()

    def _clamp_scroll(self):
        row_h = 32
        total = max(0, len(self.frames) * row_h - (self.H - 200))
        self.scroll = max(0, min(self.scroll, total))

    def _layout(self):
        rx = self.W - self.RIGHT_W
        inp_w = self.RIGHT_W - 40 - 110
        browse_w = 100

        return {
            "btn_add":    pygame.Rect(0, 0, self.BTN_W, 50),
            "btn_del":    pygame.Rect(0, 50, self.BTN_W, 50),
            "list":       pygame.Rect(0, 180, self.BTN_W, self.H - 180),
            "preview":    pygame.Rect(self.BTN_W, 0,
                                      self.W - self.BTN_W - self.RIGHT_W, self.H),
            "right":      pygame.Rect(rx, 0, self.RIGHT_W, self.H),
            "inp_name":   pygame.Rect(rx + 20, 70, self.RIGHT_W - 40, 38),
            "inp_path":   pygame.Rect(rx + 20, 170, inp_w, 38),
            "btn_browse": pygame.Rect(rx + 20 + inp_w + 10, 170, browse_w, 38),
            "chk_trim":   pygame.Rect(rx + 20, 250, 24, 24),
            "btn_save":   pygame.Rect(rx + 20, 320, self.RIGHT_W - 40, 60),
        }

    def _on_click(self, pos):
        L = self._layout()

        if L["btn_add"].collidepoint(pos):
            self.add_frames()
            return
        if L["btn_del"].collidepoint(pos):
            self.delete_selected()
            return

        if L["list"].collidepoint(pos):
            idx = (pos[1] - L["list"].y + self.scroll) // 32
            if 0 <= idx < len(self.frames):
                self.selected = idx
            return

        if L["inp_name"].collidepoint(pos):
            self.active_field = "name"
            return
        if L["inp_path"].collidepoint(pos):
            self.active_field = "path"
            return
        if L["btn_browse"].collidepoint(pos):
            self.browse_output()
            return
        if L["chk_trim"].collidepoint(pos):
            self.do_trim = not self.do_trim
            return
        if L["btn_save"].collidepoint(pos):
            self.do_save()
            return

        self.active_field = None

    def draw_button(self, rect, text, color, tcol=None):
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, self.C_DARK, rect, 3, border_radius=6)
        col = tcol or self.C_DARK
        t = self.font_b.render(text, True, col)
        self.screen.blit(
            t,
            (rect.centerx - t.get_width() // 2,
             rect.centery - t.get_height() // 2)
        )

    def draw_input(self, rect, text, active):
        pygame.draw.rect(self.screen, self.C_INPUT, rect, border_radius=4)
        pygame.draw.rect(
            self.screen,
            self.C_ACCENT if active else self.C_GREY,
            rect, 2, border_radius=4
        )

        self.screen.set_clip(rect.inflate(-8, -4))
        display = text
        while display and self.font.render(
                display, True, self.C_WHITE).get_width() > rect.w - 16:
            display = display[1:]
        self.screen.blit(
            self.font.render(display, True, self.C_WHITE),
            (rect.x + 8, rect.y + 9)
        )
        self.screen.set_clip(None)

    def draw(self):
        L = self._layout()
        self.screen.fill(self.C_BG)

        pygame.draw.rect(
            self.screen, self.C_PANEL,
            pygame.Rect(0, 0, self.BTN_W, self.H)
        )
        self.draw_button(L["btn_add"], "ДОБАВИТЬ КАДР", self.C_GREEN)
        self.draw_button(L["btn_del"], "УДАЛИТЬ КАДР", self.C_RED,
                         tcol=self.C_WHITE)

        lbl = self.font_b.render("СПИСОК КАДРОВ", True, self.C_WHITE)
        self.screen.blit(lbl, (10, 115))

        pygame.draw.line(self.screen, self.C_WHITE,
                         (self.BTN_W // 2, 145),
                         (self.BTN_W // 2, 160), 3)
        pygame.draw.polygon(self.screen, self.C_WHITE, [
            (self.BTN_W // 2 - 8, 155),
            (self.BTN_W // 2 + 8, 155),
            (self.BTN_W // 2, 170),
        ])

        list_rect = L["list"]
        pygame.draw.rect(self.screen, self.C_DARK, list_rect)
        self.screen.set_clip(list_rect)

        row_h = 32
        for i, f in enumerate(self.frames):
            y = list_rect.y + i * row_h - self.scroll
            if y + row_h < list_rect.y or y > list_rect.bottom:
                continue

            r = pygame.Rect(0, y, self.BTN_W, row_h)
            if i == self.selected:
                pygame.draw.rect(self.screen, self.C_ACCENT, r)
            elif i % 2:
                pygame.draw.rect(self.screen, self.C_PANEL, r)

            text = self.font_s.render(f["name"], True, self.C_WHITE)
            self.screen.blit(text, (10, y + 8))

        self.screen.set_clip(None)

        pv = L["preview"]
        pygame.draw.rect(self.screen, (70, 70, 70), pv)

        tile = 16
        for yy in range(pv.y, pv.bottom, tile):
            for xx in range(pv.x, pv.right, tile):
                if ((xx - pv.x) // tile + (yy - pv.y) // tile) % 2:
                    pygame.draw.rect(
                        self.screen, (55, 55, 55),
                        (xx, yy, tile, tile)
                    )

        if 0 <= self.selected < len(self.frames):
            surf = self.frames[self.selected]["surface"]
            sw, sh = surf.get_size()

            scale = min((pv.w - 40) / sw, (pv.h - 40) / sh, 4.0)
            scale = max(scale, 0.05)
            scaled = pygame.transform.scale(
                surf, (int(sw * scale), int(sh * scale))
            )

            cx = pv.x + (pv.w - scaled.get_width()) // 2
            cy = pv.y + (pv.h - scaled.get_height()) // 2

            frame_r = pygame.Rect(
                cx - 6, cy - 6,
                scaled.get_width() + 12,
                scaled.get_height() + 12
            )
            pygame.draw.rect(self.screen, self.C_ACCENT, frame_r, 2)
            self.screen.blit(scaled, (cx, cy))

            info = self.font_s.render(
                f"{sw} x {sh} px   |   масштаб: {scale:.2f}x",
                True, self.C_WHITE
            )
            self.screen.blit(info, (pv.x + 12, pv.y + 12))
        else:
            txt = self.font_B.render("ПРЕДПРОСМОТР", True, self.C_GREY)
            self.screen.blit(
                txt,
                (pv.centerx - txt.get_width() // 2,
                 pv.centery - txt.get_height() // 2)
            )

        rt = L["right"]
        pygame.draw.rect(self.screen, self.C_PANEL, rt)

        title = self.font_B.render("FUNKIN XML", True, self.C_ACCENT)
        self.screen.blit(title, (rt.x + 20, 15))

        self.screen.blit(
            self.font_b.render("ИМЯ:", True, self.C_WHITE),
            (rt.x + 20, 40)
        )
        self.draw_input(
            L["inp_name"], self.name_text,
            self.active_field == "name"
        )

        self.screen.blit(
            self.font_b.render("МЕСТО СОХРАНЕНИЯ:", True, self.C_WHITE),
            (rt.x + 20, 135)
        )
        self.draw_input(
            L["inp_path"], self.path_text,
            self.active_field == "path"
        )
        self.draw_button(
            L["btn_browse"], "ОБЗОР",
            self.C_BLUE, tcol=self.C_WHITE
        )

        chk = L["chk_trim"]
        pygame.draw.rect(self.screen, self.C_INPUT, chk, border_radius=3)
        pygame.draw.rect(self.screen, self.C_WHITE, chk, 2, border_radius=3)

        if self.do_trim:
            pygame.draw.line(
                self.screen, self.C_GREEN,
                (chk.x + 4, chk.y + 12),
                (chk.x + 10, chk.y + 18), 3
            )
            pygame.draw.line(
                self.screen, self.C_GREEN,
                (chk.x + 10, chk.y + 18),
                (chk.x + 20, chk.y + 4), 3
            )

        self.screen.blit(
            self.font.render("обрезать пустые поля?", True, self.C_WHITE),
            (chk.right + 10, chk.y + 2)
        )

        self.draw_button(L["btn_save"], "СОХРАНИТЬ", self.C_GREEN)

        msg = self.message
        max_w = rt.w - 40
        m_surf = self.font_s.render(msg, True, self.C_WHITE)
        if m_surf.get_width() > max_w:
            s = msg
            while s and self.font_s.render(
                    s + "...", True, self.C_WHITE).get_width() > max_w:
                s = s[:-1]
            m_surf = self.font_s.render(s + "...", True, self.C_WHITE)
        self.screen.blit(
            m_surf,
            (rt.x + 20, L["btn_save"].bottom + 15)
        )

        hint = self.font_s.render(
            "ZIP содержит: имя.xml + имя.png", True, self.C_GREY
        )
        self.screen.blit(hint, (rt.x + 20, rt.bottom - 30))

        pygame.display.flip()

    def run(self):
        while self.running:
            for ev in pygame.event.get():
                self.handle_event(ev)
            self.draw()
            self.clock.tick(60)
        pygame.quit()


def main():
    FunkinXMLGenerator().run()


if __name__ == "__main__":
    main()