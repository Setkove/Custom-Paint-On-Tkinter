import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, font, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageGrab
import copy
import os

# ---------- LAYER SYSTEM ----------

class Layer:
    def __init__(self, width, height, name="Layer"):
        self.name = name
        self.visible = True
        self.image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

class LayerManager:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.layers = []
        self.current_index = 0

        # создаём базовый слой
        self.add_layer("Background")

    def add_layer(self, name="Layer"):
        layer = Layer(self.width, self.height, name)
        self.layers.append(layer)
        self.current_index = len(self.layers) - 1

    def delete_layer(self, index=None):
        if index is None:
            index = self.current_index
        if len(self.layers) <= 1:
            return  # нельзя удалить последний слой
        del self.layers[index]
        self.current_index = max(0, self.current_index - 1)

    def toggle_visibility(self, index=None):
        if index is None:
            index = self.current_index
        self.layers[index].visible = not self.layers[index].visible

    def set_current(self, index):
        if 0 <= index < len(self.layers):
            self.current_index = index

    def get_current_layer(self):
        return self.layers[self.current_index]

    def composite(self):
        base = Image.new("RGBA", (self.width, self.height), (255, 255, 255, 255))
        for layer in self.layers:
            if layer.visible:
                base.alpha_composite(layer.image)
        return base

# ---------- HISTORY (UNDO/REDO) ----------

class History:
    def __init__(self, layer_manager: LayerManager):
        self.layer_manager = layer_manager
        self.undo_stack = []
        self.redo_stack = []

    def snapshot(self):
        # сохраняем копию всех слоёв
        snap = [copy.deepcopy(layer.image) for layer in self.layer_manager.layers]
        self.undo_stack.append(snap)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        current = [copy.deepcopy(layer.image) for layer in self.layer_manager.layers]
        self.redo_stack.append(current)

        snap = self.undo_stack.pop()
        for i, img in enumerate(snap):
            if i < len(self.layer_manager.layers):
                self.layer_manager.layers[i].image = img

    def redo(self):
        if not self.redo_stack:
            return
        current = [copy.deepcopy(layer.image) for layer in self.layer_manager.layers]
        self.undo_stack.append(current)

        snap = self.redo_stack.pop()
        for i, img in enumerate(snap):
            if i < len(self.layer_manager.layers):
                self.layer_manager.layers[i].image = img

# ---------- CORE PAINT ENGINE ----------

class PaintCore:
    def __init__(self, root, width=1500, height=1000):
        self.root = root
        self.width = width
        self.height = height

        # ядро: слои + история
        self.layers = LayerManager(width, height)
        self.history = History(self.layers)

        # текущий инструмент (пока заглушка)
        self.current_tool = None

        # canvas
        self.canvas = tk.Canvas(root, bg="white", width=width, height=height)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # zoom
        self.zoom = 1.0

        # мышь
        self.start_x = None
        self.start_y = None

        # бинды
        self.canvas.bind("<Button-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)

        self.redraw()

    # ---------- RENDER ----------
    def set_tool(self, tool):
        self.current_tool = tool

    def redraw(self):
        img = self.layers.composite()
        self.display_image = img
        self.tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

    # ---------- ZOOM ----------
    def set_zoom(self, factor):
        scale = factor / self.zoom
        self.zoom = factor
        self.canvas.scale("all", 0, 0, scale, scale)

    # ---------- MOUSE ----------
    def on_left_down(self, event):
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        self.start_x, self.start_y = x, y

        # перед любым действием — snapshot
        self.history.snapshot()

        if self.current_tool:
            self.current_tool.on_press(self, x, y)

    def on_left_drag(self, event):
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        if self.current_tool:
            self.current_tool.on_drag(self, x, y)

    def on_left_up(self, event):
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        if self.current_tool:
            self.current_tool.on_release(self, x, y)

    # ---------- FILE OPS ----------
    def open_image_to_background(self, path):
        img = Image.open(path).convert("RGBA")
        img = img.resize((self.width, self.height))
        self.layers.layers[0].image = img
        self.redraw()

    def save_flattened(self, path):
        img = self.layers.composite()
        ext = os.path.splitext(path)[1].lower()
        if ext == ".psd":
            # заглушка: сохраняем как PNG рядом
            png_path = path.replace(".psd", ".png")
            img.save(png_path)
            messagebox.showinfo("Save", f"PSD заглушка: сохранено как PNG: {png_path}")
        else:
            img.save(path)
            messagebox.showinfo("Save", f"Saved to {path}")
from PIL import ImageDraw, ImageFont

# ============================================================
# BRUSH TOOL
# ============================================================

class BrushTool:
    def __init__(self, size=10, color="#000000", shape="circle"):
        self.size = size
        self.color = color
        self.shape = shape

    def on_press(self, core, x, y):
        self.draw(core, x, y)

    def on_drag(self, core, x, y):
        self.draw(core, x, y)

    def on_release(self, core, x, y):
        pass

    def draw(self, core, x, y):
        draw = ImageDraw.Draw(core.layers.get_current_layer().image)
        r = self.size // 2

        if self.shape == "circle":
            draw.ellipse((x - r, y - r, x + r, y + r), fill=self.color)
        else:
            draw.rectangle((x - r, y - r, x + r, y + r), fill=self.color)

        core.redraw()


# ============================================================
# BUCKET FILL TOOL (FLOOD FILL)
# ============================================================

class BucketFillTool:
    def __init__(self, fill_color="#000000"):
        self.fill_color = fill_color

    def on_press(self, core, x, y):
        self.flood_fill(core, x, y)
        core.redraw()

    def on_drag(self, core, x, y):
        pass

    def on_release(self, core, x, y):
        pass

    def flood_fill(self, core, x, y):
        img = core.layers.get_current_layer().image
        target = img.getpixel((x, y))
        new = self.hex_to_rgba(self.fill_color)

        if target == new:
            return

        w, h = img.size
        stack = [(x, y)]
        px = img.load()

        while stack:
            cx, cy = stack.pop()
            if cx < 0 or cy < 0 or cx >= w or cy >= h:
                continue
            if px[cx, cy] != target:
                continue

            px[cx, cy] = new

            stack.append((cx + 1, cy))
            stack.append((cx - 1, cy))
            stack.append((cx, cy + 1))
            stack.append((cx, cy - 1))

    def hex_to_rgba(self, hex_color):
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b, 255)


# ============================================================
# RECT TOOL
# ============================================================

class RectTool:
    def __init__(self, outline="#000000", fill=""):
        self.outline = outline
        self.fill = fill
        self.start_x = None
        self.start_y = None

    def on_press(self, core, x, y):
        self.start_x = x
        self.start_y = y

    def on_drag(self, core, x, y):
        core.redraw()
        draw = ImageDraw.Draw(core.display_image)
        draw.rectangle((self.start_x, self.start_y, x, y),
                       outline=self.outline,
                       fill=self.fill if self.fill else None)
        core.tk_image = ImageTk.PhotoImage(core.display_image)
        core.canvas.create_image(0, 0, image=core.tk_image, anchor="nw")

    def on_release(self, core, x, y):
        draw = ImageDraw.Draw(core.layers.get_current_layer().image)
        draw.rectangle((self.start_x, self.start_y, x, y),
                       outline=self.outline,
                       fill=self.fill if self.fill else None)
        core.redraw()


# ============================================================
# OVAL TOOL
# ============================================================

class OvalTool:
    def __init__(self, outline="#000000", fill=""):
        self.outline = outline
        self.fill = fill
        self.start_x = None
        self.start_y = None

    def on_press(self, core, x, y):
        self.start_x = x
        self.start_y = y

    def on_drag(self, core, x, y):
        core.redraw()
        draw = ImageDraw.Draw(core.display_image)
        draw.ellipse((self.start_x, self.start_y, x, y),
                     outline=self.outline,
                     fill=self.fill if self.fill else None)
        core.tk_image = ImageTk.PhotoImage(core.display_image)
        core.canvas.create_image(0, 0, image=core.tk_image, anchor="nw")

    def on_release(self, core, x, y):
        draw = ImageDraw.Draw(core.layers.get_current_layer().image)
        draw.ellipse((self.start_x, self.start_y, x, y),
                     outline=self.outline,
                     fill=self.fill if self.fill else None)
        core.redraw()


# ============================================================
# POLYGON TOOL
# ============================================================

class PolygonTool:
    def __init__(self, outline="#000000", fill=""):
        self.outline = outline
        self.fill = fill
        self.points = []

    def on_press(self, core, x, y):
        self.points.append((x, y))
        core.redraw()
        draw = ImageDraw.Draw(core.display_image)
        if len(self.points) > 1:
            draw.line((self.points[-2], self.points[-1]), fill=self.outline, width=2)
        core.tk_image = ImageTk.PhotoImage(core.display_image)
        core.canvas.create_image(0, 0, image=core.tk_image, anchor="nw")

    def on_drag(self, core, x, y):
        pass

    def on_release(self, core, x, y):
        pass

    def finish(self, core):
        if len(self.points) >= 3:
            draw = ImageDraw.Draw(core.layers.get_current_layer().image)
            draw.polygon(self.points,
                         outline=self.outline,
                         fill=self.fill if self.fill else None)
            core.redraw()
        self.points = []


# ============================================================
# TEXT TOOL
# ============================================================

class TextTool:
    def __init__(self, font_family="Segoe UI", size=20,
                 bold=False, italic=False, outline=False,
                 color="#000000", fill=""):
        self.font_family = font_family
        self.size = size
        self.bold = bold
        self.italic = italic
        self.outline = outline
        self.color = color
        self.fill = fill

    def on_press(self, core, x, y):
        self.insert_text(core, x, y)

    def on_drag(self, core, x, y):
        pass

    def on_release(self, core, x, y):
        pass

    def insert_text(self, core, x, y):
        win = tk.Toplevel(core.root)
        win.title("Text")

        txt = tk.Text(win, width=40, height=4)
        txt.pack()

        def ok():
            content = txt.get("1.0", tk.END).strip()
            if content:
                self.draw_text(core, content, x, y)
                core.redraw()
            win.destroy()

        ttk.Button(win, text="OK", command=ok).pack()

    def draw_text(self, core, text, x, y):
        img = core.layers.get_current_layer().image
        draw = ImageDraw.Draw(img)

        try:
            fnt = ImageFont.truetype(self.font_family, self.size)
        except:
            fnt = ImageFont.load_default()

        # outline
        if self.outline:
            offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for dx, dy in offsets:
                draw.text((x + dx, y + dy), text, font=fnt, fill=self.color)

        fill_color = self.fill if self.fill else self.color
        draw.text((x, y), text, font=fnt, fill=fill_color)

# ============================================================
# TOOLBAR UI
# ============================================================

class ToolbarUI:
    def __init__(self, root, core, tools):
        self.root = root
        self.core = core
        self.tools = tools

        frame = ttk.Frame(root)
        frame.pack(side=tk.TOP, fill=tk.X)

        # инструменты
        ttk.Button(frame, text="Brush", command=lambda: core.set_tool(tools["brush"])).pack(side=tk.LEFT)
        ttk.Button(frame, text="Bucket", command=lambda: core.set_tool(tools["bucket"])).pack(side=tk.LEFT)
        ttk.Button(frame, text="Rect", command=lambda: core.set_tool(tools["rect"])).pack(side=tk.LEFT)
        ttk.Button(frame, text="Oval", command=lambda: core.set_tool(tools["oval"])).pack(side=tk.LEFT)
        ttk.Button(frame, text="Polygon", command=lambda: core.set_tool(tools["polygon"])).pack(side=tk.LEFT)
        ttk.Button(frame, text="Text", command=lambda: core.set_tool(tools["text"])).pack(side=tk.LEFT)

        # brush size
        ttk.Label(frame, text="Size:").pack(side=tk.LEFT, padx=5)
        self.size_var = tk.IntVar(value=tools["brush"].size)
        ttk.Spinbox(frame, from_=1, to=100, textvariable=self.size_var,
                    width=4, command=self.update_brush_size).pack(side=tk.LEFT)

        # brush shape
        ttk.Label(frame, text="Shape:").pack(side=tk.LEFT)
        self.shape_var = tk.StringVar(value=tools["brush"].shape)
        ttk.Combobox(frame, values=["circle", "square"],
                     textvariable=self.shape_var, width=8,
                     state="readonly").pack(side=tk.LEFT)

        # outline / fill
        ttk.Button(frame, text="Outline", command=self.choose_outline).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="Fill", command=self.choose_fill).pack(side=tk.LEFT)
        ttk.Button(frame, text="No Fill", command=self.clear_fill).pack(side=tk.LEFT)

        # zoom
        ttk.Label(frame, text="Zoom:").pack(side=tk.LEFT, padx=5)
        self.zoom_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(frame, from_=0.25, to=4.0, increment=0.25,
                    textvariable=self.zoom_var, width=5,
                    command=self.apply_zoom).pack(side=tk.LEFT)

        # text font
        ttk.Label(frame, text="Font:").pack(side=tk.LEFT, padx=5)
        self.font_var = tk.StringVar(value=tools["text"].font_family)
        ttk.Combobox(frame, values=sorted(font.families()),
                     textvariable=self.font_var, width=15).pack(side=tk.LEFT)

        ttk.Label(frame, text="Size:").pack(side=tk.LEFT)
        self.font_size_var = tk.IntVar(value=tools["text"].size)
        ttk.Spinbox(frame, from_=6, to=72, textvariable=self.font_size_var,
                    width=4, command=self.update_text_size).pack(side=tk.LEFT)

        # bold / italic / outline
        self.bold_var = tk.BooleanVar(value=tools["text"].bold)
        ttk.Checkbutton(frame, text="Bold", variable=self.bold_var,
                        command=self.update_text_style).pack(side=tk.LEFT)
        self.italic_var = tk.BooleanVar(value=tools["text"].italic)
        ttk.Checkbutton(frame, text="Italic", variable=self.italic_var,
                        command=self.update_text_style).pack(side=tk.LEFT)
        self.outline_var = tk.BooleanVar(value=tools["text"].outline)
        ttk.Checkbutton(frame, text="Outline", variable=self.outline_var,
                        command=self.update_text_style).pack(side=tk.LEFT)

        self.tools = tools

    # --- brush ---
    def update_brush_size(self):
        self.tools["brush"].size = self.size_var.get()

    def choose_outline(self):
        c = colorchooser.askcolor()[1]
        if c:
            self.tools["brush"].color = c
            self.tools["rect"].outline = c
            self.tools["oval"].outline = c
            self.tools["polygon"].outline = c
            self.tools["text"].color = c

    def choose_fill(self):
        c = colorchooser.askcolor()[1]
        if c:
            self.tools["rect"].fill = c
            self.tools["oval"].fill = c
            self.tools["polygon"].fill = c
            self.tools["text"].fill = c
            self.tools["bucket"].fill_color = c

    def clear_fill(self):
        self.tools["rect"].fill = ""
        self.tools["oval"].fill = ""
        self.tools["polygon"].fill = ""
        self.tools["text"].fill = ""

    def apply_zoom(self):
        self.core.set_zoom(self.zoom_var.get())

    # --- text ---
    def update_text_size(self):
        self.tools["text"].size = self.font_size_var.get()

    def update_text_style(self):
        self.tools["text"].bold = self.bold_var.get()
        self.tools["text"].italic = self.italic_var.get()
        self.tools["text"].outline = self.outline_var.get()


# ============================================================
# PROPERTIES PANEL
# ============================================================

class PropertiesPanelUI:
    def __init__(self, root, tools):
        self.root = root
        self.tools = tools
        self.window = None

    def show(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.lift()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("Properties")

        ttk.Label(self.window, text="Brush size:").pack(anchor="w")
        size_var = tk.IntVar(value=self.tools["brush"].size)
        ttk.Spinbox(self.window, from_=1, to=100, textvariable=size_var,
                    command=lambda: self.set_brush_size(size_var.get())).pack(anchor="w")

        ttk.Label(self.window, text="Brush shape:").pack(anchor="w")
        shape_var = tk.StringVar(value=self.tools["brush"].shape)
        ttk.Combobox(self.window, values=["circle", "square"],
                     textvariable=shape_var, state="readonly",
                     width=10,
                     command=lambda: self.set_brush_shape(shape_var.get())).pack(anchor="w")

        ttk.Button(self.window, text="Outline color",
                   command=self.choose_outline).pack(anchor="w", pady=5)
        ttk.Button(self.window, text="Fill color",
                   command=self.choose_fill).pack(anchor="w")
        ttk.Button(self.window, text="No fill",
                   command=self.clear_fill).pack(anchor="w")

    def set_brush_size(self, v):
        self.tools["brush"].size = v

    def set_brush_shape(self, v):
        self.tools["brush"].shape = v

    def choose_outline(self):
        c = colorchooser.askcolor()[1]
        if c:
            self.tools["brush"].color = c
            self.tools["rect"].outline = c
            self.tools["oval"].outline = c
            self.tools["polygon"].outline = c
            self.tools["text"].color = c

    def choose_fill(self):
        c = colorchooser.askcolor()[1]
        if c:
            self.tools["rect"].fill = c
            self.tools["oval"].fill = c
            self.tools["polygon"].fill = c
            self.tools["text"].fill = c
            self.tools["bucket"].fill_color = c

    def clear_fill(self):
        self.tools["rect"].fill = ""
        self.tools["oval"].fill = ""
        self.tools["polygon"].fill = ""
        self.tools["text"].fill = ""


# ============================================================
# LAYERS PANEL
# ============================================================

class LayersPanelUI:
    def __init__(self, root, core):
        self.root = root
        self.core = core
        self.window = None

    def show(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.lift()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("Layers")

        self.listbox = tk.Listbox(self.window)
        self.listbox.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Add Layer", command=self.add_layer).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Delete Layer", command=self.delete_layer).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Toggle Visibility", command=self.toggle_visibility).pack(side=tk.LEFT)

        self.refresh()

        self.listbox.bind("<<ListboxSelect>>", self.on_select)

    def refresh(self):
        if not self.window or not tk.Toplevel.winfo_exists(self.window):
            return
        self.listbox.delete(0, tk.END)
        for i, layer in enumerate(self.core.layers.layers):
            vis = "👁" if layer.visible else "🚫"
            mark = "*" if i == self.core.layers.current_index else " "
            self.listbox.insert(tk.END, f"{mark} {layer.name} {vis}")

    def add_layer(self):
        self.core.layers.add_layer(f"Layer {len(self.core.layers.layers)}")
        self.refresh()
        self.core.redraw()

    def delete_layer(self):
        self.core.layers.delete_layer()
        self.refresh()
        self.core.redraw()

    def toggle_visibility(self):
        self.core.layers.toggle_visibility()
        self.refresh()
        self.core.redraw()

    def on_select(self, event):
        sel = self.listbox.curselection()
        if sel:
            self.core.layers.set_current(sel[0])
            self.refresh()
            self.core.redraw()


# ============================================================
# MAIN APP (собирает всё)
# ============================================================

class PaintApp:
    def __init__(self, root):
        # ядро
        self.core = PaintCore(root)

        # инструменты
        self.tools = {
            "brush": BrushTool(),
            "bucket": BucketFillTool(),
            "rect": RectTool(),
            "oval": OvalTool(),
            "polygon": PolygonTool(),
            "text": TextTool()
        }

        # тулбар
        self.toolbar = ToolbarUI(root, self.core, self.tools)

        # панели
        self.properties_panel = PropertiesPanelUI(root, self.tools)
        self.layers_panel = LayersPanelUI(root, self.core)

        # меню
        self.build_menu(root)

    def build_menu(self, root):
        menubar = tk.Menu(root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image", command=self.open_image)
        file_menu.add_command(label="Save As...", command=self.save_image)
        file_menu.add_separator()
        file_menu.add_command(label="Show Properties Panel", command=self.properties_panel.show)
        file_menu.add_command(label="Show Layers Panel", command=self.layers_panel.show)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.undo)
        edit_menu.add_command(label="Redo", command=self.redo)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        root.config(menu=menubar)

    def undo(self):
        self.core.history.undo()
        self.core.redraw()

    def redo(self):
        self.core.history.redo()
        self.core.redraw()

    def open_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
        )
        if not path:
            return
        self.core.open_image_to_background(path)

    def save_image(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg;*.jpeg"),
                ("Bitmap", "*.bmp"),
                ("GIF", "*.gif"),
                ("PSD (flattened)", "*.psd"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return
        self.core.save_flattened(path)

# ============================================================
# MAIN — Paint Engine Launcher
# ============================================================

import tkinter as tk

# ядро
# (сюда вставляются классы из Часть 1)
# Layer, LayerManager, History, PaintCore

# инструменты
# (сюда вставляются классы из Часть 2)
# BrushTool, BucketFillTool, RectTool, OvalTool, PolygonTool, TextTool

# UI
# (сюда вставляются классы из Часть 3)
# ToolbarUI, PropertiesPanelUI, LayersPanelUI


class PaintApp:
    def __init__(self, root):
        # ядро
        self.core = PaintCore(root)

        # инструменты
        self.tools = {
            "brush": BrushTool(),
            "bucket": BucketFillTool(),
            "rect": RectTool(),
            "oval": OvalTool(),
            "polygon": PolygonTool(),
            "text": TextTool()
        }

        # тулбар
        self.toolbar = ToolbarUI(root, self.core, self.tools)

        # панели
        self.properties_panel = PropertiesPanelUI(root, self.tools)
        self.layers_panel = LayersPanelUI(root, self.core)

        # меню
        self.build_menu(root)

    def build_menu(self, root):
        menubar = tk.Menu(root)

        # FILE
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image", command=self.open_image)
        file_menu.add_command(label="Save As...", command=self.save_image)
        file_menu.add_separator()
        file_menu.add_command(label="Show Properties Panel", command=self.properties_panel.show)
        file_menu.add_command(label="Show Layers Panel", command=self.layers_panel.show)
        menubar.add_cascade(label="File", menu=file_menu)

        # EDIT
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.undo)
        edit_menu.add_command(label="Redo", command=self.redo)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        root.config(menu=menubar)

    def undo(self):
        self.core.history.undo()
        self.core.redraw()

    def redo(self):
        self.core.history.redo()
        self.core.redraw()

    def open_image(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
        )
        if not path:
            return
        self.core.open_image_to_background(path)

    def save_image(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg;*.jpeg"),
                ("Bitmap", "*.bmp"),
                ("GIF", "*.gif"),
                ("PSD (flattened)", "*.psd"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return
        self.core.save_flattened(path)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    root.title("TkPaint Engine")
    root.attributes("-fullscreen", True)
    app = PaintApp(root)
    root.mainloop()
