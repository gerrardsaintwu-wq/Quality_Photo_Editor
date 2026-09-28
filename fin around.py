from tkinter import *
from tkinter import ttk, filedialog
from PIL import ImageTk, Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import os

# --- GLOBAL VARIABLES FOR UI & HISTORY STATE ---
current_mode = None       
bbox = [0, 0, 0, 0]       
active_handle = None      
handle_size = 12          

# Viewport Tracking
img_canvas_x = 0          
img_canvas_y = 0          
scale_factor = 1.0        
zoom_level = 1.0
pan_x = 300
pan_y = 300
last_pan_x = 0
last_pan_y = 0

checkerboard_bg = None    
clean_disp_img = None     
image_item_id = None      
preview_tk = None         

action_history = []       
current_step = 0          
base_image = None         

is_rendering = False
slider_start_vals = {}    


def generate_checkerboard():
    """Generates a gray and white checkered background for transparent/blank spaces."""
    base = Image.new('RGB', (40, 40), color='#ffffff')
    draw = ImageDraw.Draw(base)
    draw.rectangle([20, 0, 39, 19], fill='#cccccc')
    draw.rectangle([0, 20, 19, 39], fill='#cccccc')
    
    cb = Image.new('RGB', (600, 600))
    for y in range(0, 600, 40):
        for x in range(0, 600, 40):
            cb.paste(base, (x, y))
    return ImageTk.PhotoImage(cb)

def reset_viewport(img):
    """Auto-fits newly loaded images to the screen so massive files aren't cut off."""
    global zoom_level, pan_x, pan_y
    w, h = img.size
    zoom_level = min(500/w, 500/h, 1.0)
    pan_x, pan_y = 300, 300

def displayimage(img_to_display):
    """Updates the Tkinter canvas using true Zoom and Pan positioning."""
    global dispimage, img_canvas_x, img_canvas_y, scale_factor, checkerboard_bg, clean_disp_img, image_item_id
    
    if checkerboard_bg is None:
        checkerboard_bg = generate_checkerboard()

    ow, oh = img_to_display.size
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS
        
    dw = int(ow * zoom_level)
    dh = int(oh * zoom_level)
    
    dw = max(1, dw)
    dh = max(1, dh)
    
    disp_img = img_to_display.resize((dw, dh), resample)
    
    clean_disp_img = disp_img.copy()
    dispimage = ImageTk.PhotoImage(disp_img)
    
    scale_factor = zoom_level
    
    img_canvas_x = pan_x - dw / 2
    img_canvas_y = pan_y - dh / 2
    
    panel.delete("all")
    panel.create_image(300, 300, image=checkerboard_bg, anchor=CENTER)
    image_item_id = panel.create_image(pan_x, pan_y, image=dispimage, anchor=CENTER)
    panel.image = dispimage 
    
    draw_rulers(ow, oh)
    
    if current_mode in ['crop', 'resize']:
        draw_handles()

def draw_rulers(ow, oh):
    """Draws axis rulers and updates the dimension status label."""
    panel.create_rectangle(0, 0, 600, 22, fill='#1f242d', outline='#4f5b66') 
    panel.create_rectangle(0, 0, 22, 600, fill='#1f242d', outline='#4f5b66') 
    panel.create_rectangle(0, 0, 22, 22, fill='#14181d', outline='#4f5b66')  
    
    step = 100
    if zoom_level < 0.3: step = 500
    elif zoom_level < 0.7: step = 200
    elif zoom_level > 2.0: step = 50
    elif zoom_level > 5.0: step = 10
    
    img_left = img_canvas_x
    for x_val in range(0, ow + 1, step):
        canvas_x = img_left + (x_val * scale_factor)
        if 22 <= canvas_x <= 600:
            panel.create_line(canvas_x, 15, canvas_x, 22, fill='white')
            if x_val > 0:
                panel.create_text(canvas_x, 8, text=str(x_val), fill='#a0a0a0', font=('Arial', 7))
                
    img_top = img_canvas_y
    for y_val in range(0, oh + 1, step):
        canvas_y = img_top + (y_val * scale_factor)
        if 22 <= canvas_y <= 600:
            panel.create_line(15, canvas_y, 22, canvas_y, fill='white')
            if y_val > 0:
                panel.create_text(10, canvas_y, text=str(y_val), fill='#a0a0a0', font=('Arial', 7), angle=90)

    dim_label.config(text=f"Image Size: {ow} x {oh} px  |  Zoom: {int(zoom_level * 100)}%")

def track_mouse(event):
    """Tracks mouse movement over the canvas and shows live pixel coordinates."""
    if not clean_disp_img: return
    
    img_x = int((event.x - img_canvas_x) / scale_factor)
    img_y = int((event.y - img_canvas_y) / scale_factor)
    
    ow, oh = img.size
    if 0 <= img_x < ow and 0 <= img_y < oh:
        coord_label.config(text=f"Cursor: X: {img_x}, Y: {img_y} px")
    else:
        coord_label.config(text="Cursor: Outside Image")

# --- ZOOM & PAN CONTROLS ---

def zoom(event):
    """Zooms in and out with the mouse wheel, centering on the cursor."""
    global zoom_level, pan_x, pan_y
    
    if current_mode in ['crop', 'resize']:
        cancel_action()
        
    old_zoom = zoom_level
    
    if event.num == 4 or getattr(event, 'delta', 0) > 0:
        zoom_level *= 1.15
    elif event.num == 5 or getattr(event, 'delta', 0) < 0:
        zoom_level /= 1.15
        
    zoom_level = max(0.01, min(zoom_level, 50.0))
    
    scale_ratio = zoom_level / old_zoom
    pan_x = event.x - (event.x - pan_x) * scale_ratio
    pan_y = event.y - (event.y - pan_y) * scale_ratio
    
    displayimage(outputImage)

def start_pan(event):
    global last_pan_x, last_pan_y
    last_pan_x, last_pan_y = event.x, event.y

def do_pan(event):
    global pan_x, pan_y, last_pan_x, last_pan_y
    dx = event.x - last_pan_x
    dy = event.y - last_pan_y
    pan_x += dx
    pan_y += dy
    last_pan_x, last_pan_y = event.x, event.y
    displayimage(outputImage)


def draw_handles():
    """Draws the bounding box and provides real-time image manipulation feedback."""
    global preview_tk
    panel.delete("overlay") 
    x1, x2 = sorted([bbox[0], bbox[2]])
    y1, y2 = sorted([bbox[1], bbox[3]])
    
    if current_mode == 'resize':
        color = 'cyan'
        w = int(max(1, x2 - x1))
        h = int(max(1, y2 - y1))
        if clean_disp_img and image_item_id:
            preview = clean_disp_img.resize((w, h), Image.NEAREST)
            preview_tk = ImageTk.PhotoImage(preview)
            panel.itemconfig(image_item_id, image=preview_tk)
            panel.coords(image_item_id, (x1+x2)/2, (y1+y2)/2)
            
    elif current_mode == 'crop':
        color = 'magenta'
        if clean_disp_img:
            ix1, iy1 = img_canvas_x, img_canvas_y
            ix2, iy2 = img_canvas_x + clean_disp_img.width, img_canvas_y + clean_disp_img.height
            
            cx1, cy1 = max(ix1, min(ix2, x1)), max(iy1, min(iy2, y1))
            cx2, cy2 = max(ix1, min(ix2, x2)), max(iy1, min(iy2, y2))
            
            panel.create_rectangle(ix1, iy1, ix2, cy1, fill='black', stipple='gray50', outline='', tags="overlay")
            panel.create_rectangle(ix1, cy2, ix2, iy2, fill='black', stipple='gray50', outline='', tags="overlay")
            panel.create_rectangle(ix1, iy1, cx1, cy2, fill='black', stipple='gray50', outline='', tags="overlay")
            panel.create_rectangle(cx2, cy1, ix2, cy2, fill='black', stipple='gray50', outline='', tags="overlay")
    else:
        color = 'cyan'
            
    panel.create_rectangle(x1, y1, x2, y2, outline=color, width=2, dash=(4,4), tags="overlay")
    
    s = handle_size / 2
    panel.create_rectangle(x1-s, y1-s, x1+s, y1+s, fill=color, tags="overlay") 
    panel.create_rectangle(x2-s, y1-s, x2+s, y1+s, fill=color, tags="overlay") 
    panel.create_rectangle(x1-s, y2-s, x1+s, y2+s, fill=color, tags="overlay") 
    panel.create_rectangle(x2-s, y2-s, x2+s, y2+s, fill=color, tags="overlay") 
    
    action_text = "Resize" if current_mode == 'resize' else "Crop"
    txt_id = panel.create_text(300, 35, text=f"Drag corners to {action_text}. Press ENTER to apply. (ESC to cancel)", 
                               fill="black", font=("poppins", 11, "bold"), tags="overlay")
    txt_bbox = panel.bbox(txt_id)
    panel.create_rectangle(txt_bbox[0]-5, txt_bbox[1]-2, txt_bbox[2]+5, txt_bbox[3]+2, 
                           fill="white", tags="overlay", outline="")
    panel.tag_raise(txt_id)

def activate_crop():
    global current_mode, bbox
    current_mode = 'crop'
    if not hasattr(panel, 'image'): return
    dw, dh = clean_disp_img.width, clean_disp_img.height
    pad_x, pad_y = dw * 0.1, dh * 0.1
    bbox = [img_canvas_x, img_canvas_y, img_canvas_x + dw, img_canvas_y + dh]
    panel.config(cursor="crosshair")
    displayimage(outputImage)

def activate_resize():
    global current_mode, bbox
    current_mode = 'resize'
    if not hasattr(panel, 'image'): return
    dw, dh = clean_disp_img.width, clean_disp_img.height
    bbox = [img_canvas_x, img_canvas_y, img_canvas_x + dw, img_canvas_y + dh]
    panel.config(cursor="crosshair")
    displayimage(outputImage)

def start_drag(event):
    global active_handle
    if current_mode not in ['crop', 'resize']: return
    
    x, y = event.x, event.y
    x1, y1, x2, y2 = bbox
    s = handle_size
    
    if abs(x - x1) <= s and abs(y - y1) <= s: active_handle = 'TL'
    elif abs(x - x2) <= s and abs(y - y1) <= s: active_handle = 'TR'
    elif abs(x - x1) <= s and abs(y - y2) <= s: active_handle = 'BL'
    elif abs(x - x2) <= s and abs(y - y2) <= s: active_handle = 'BR'
    else:
        active_handle = 'NEW'
        bbox[0] = bbox[2] = x
        bbox[1] = bbox[3] = y

def drag(event):
    if not current_mode or not active_handle: return
    x, y = event.x, event.y
    
    if active_handle == 'TL': bbox[0], bbox[1] = x, y
    elif active_handle == 'TR': bbox[2], bbox[1] = x, y
    elif active_handle == 'BL': bbox[0], bbox[3] = x, y
    elif active_handle == 'BR': bbox[2], bbox[3] = x, y
    elif active_handle == 'NEW': bbox[2], bbox[3] = x, y
    draw_handles()

def end_drag(event):
    global active_handle
    active_handle = None

def apply_action(event=None):
    """Executes the crop or resize when the user presses ENTER and adds it to history."""
    global current_mode
    if current_mode not in ['crop', 'resize']: return
    
    x1, x2 = sorted([bbox[0], bbox[2]])
    y1, y2 = sorted([bbox[1], bbox[3]])
    
    ox1 = (x1 - img_canvas_x) / scale_factor
    oy1 = (y1 - img_canvas_y) / scale_factor
    ox2 = (x2 - img_canvas_x) / scale_factor
    oy2 = (y2 - img_canvas_y) / scale_factor
    
    ow, oh = img.size
    ox1, oy1 = max(0, int(ox1)), max(0, int(oy1))
    ox2, oy2 = min(ow, int(ox2)), min(oh, int(oy2))
    
    temp_mode = current_mode
    current_mode = None
    panel.config(cursor="")
    
    if ox2 - ox1 < 5 or oy2 - oy1 < 5:
        displayimage(outputImage)
        return
        
    if temp_mode == 'crop':
        add_action('crop', value=(ox1, oy1, ox2, oy2))
    elif temp_mode == 'resize':
        add_action('resize', value=(ox2 - ox1, oy2 - oy1))

def cancel_action(event=None):
    """Cancels the active crop or resize operation via the ESC key."""
    global current_mode
    if current_mode in ['crop', 'resize']:
        current_mode = None
        panel.config(cursor="")
        displayimage(outputImage)

# --- UNDO / REDO ENGINE ---

def update_button_states():
    if current_step > 0:
        btnUndo.configure(state=NORMAL)
    else:
        btnUndo.configure(state=DISABLED)
        
    if current_step < len(action_history):
        btnRedo.configure(state=NORMAL)
    else:
        btnRedo.configure(state=DISABLED)

def apply_modifier(temp_img, modifier):
    action = modifier['action']
    val = modifier.get('value')
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS

    if action == 'rotate': return temp_img.rotate(90, expand=True)
    elif action == 'flip': return temp_img.transpose(Image.FLIP_LEFT_RIGHT)
    elif action == 'blur': return temp_img.filter(ImageFilter.BLUR)
    elif action == 'emboss': return temp_img.filter(ImageFilter.EMBOSS)
    elif action == 'edgeEnhance': return temp_img.filter(ImageFilter.EDGE_ENHANCE)
    elif action == 'crop': return temp_img.crop(val)
    elif action == 'resize': return temp_img.resize(val, resample)
    return temp_img

def render_state():
    """Rebuilds image state AND restores slider values corresponding to that step."""
    global img, outputImage, is_rendering
    is_rendering = True  
    
    temp_img = base_image.copy()
    slider_state = {'brightness': 1.0, 'contrast': 1.0, 'sharpness': 1.0, 'color': 1.0}
    
    for i in range(current_step):
        item = action_history[i]
        if item['action'] == 'slider':
            slider_state[item['type']] = item['value']
        else:
            temp_img = apply_modifier(temp_img, item)
        
    img = temp_img
    
    brightnessSlider.set(slider_state['brightness'])
    contrastSlider.set(slider_state['contrast'])
    sharpnessSlider.set(slider_state['sharpness'])
    colorSlider.set(slider_state['color'])
    
    is_rendering = False
    apply_sliders_to_image()

def add_action(action_name, value=None, slider_type=None):
    global current_step, action_history, base_image
    
    action_history = action_history[:current_step]
    
    entry = {'action': action_name, 'value': value}
    if slider_type:
        entry['type'] = slider_type
        
    action_history.append(entry)
    current_step += 1
    
    if len(action_history) > 50:
        oldest = action_history[0]
        if oldest['action'] != 'slider':
            base_image = apply_modifier(base_image, oldest)
        action_history.pop(0)
        current_step -= 1
        
    render_state()
    update_button_states()

def undo():
    global current_step
    if current_step > 0:
        current_step -= 1
        render_state()
        update_button_states()

def redo():
    global current_step
    if current_step < len(action_history):
        current_step += 1
        render_state()
        update_button_states()

# --- FILTERS & SLIDERS ---

def on_slider_move(val):
    if is_rendering: return
    apply_sliders_to_image()

def on_slider_press(slider_type, slider_widget):
    if is_rendering: return
    slider_start_vals[slider_type] = slider_widget.get()

def on_slider_release(slider_type, slider_widget):
    if is_rendering: return
    start_val = slider_start_vals.get(slider_type, 1.0)
    end_val = slider_widget.get()
    
    if start_val != end_val:
        add_action('slider', value=end_val, slider_type=slider_type)

def apply_sliders_to_image():
    global outputImage
    temp_img = img.copy() 
    
    b_val = brightnessSlider.get()
    if b_val != 1.0: temp_img = ImageEnhance.Brightness(temp_img).enhance(b_val)
        
    c_val = contrastSlider.get()
    if c_val != 1.0: temp_img = ImageEnhance.Contrast(temp_img).enhance(c_val)
        
    s_val = sharpnessSlider.get()
    if s_val != 1.0: temp_img = ImageEnhance.Sharpness(temp_img).enhance(s_val)
        
    col_val = colorSlider.get()
    if col_val != 1.0: temp_img = ImageEnhance.Color(temp_img).enhance(col_val)
        
    outputImage = temp_img
    displayimage(outputImage)

def rotate(): add_action('rotate')
def flip(): add_action('flip')
def blurr(): add_action('blur')
def emboss(): add_action('emboss')
def edgeEnhance(): add_action('edgeEnhance')

def reset():
    global current_mode, action_history, current_step, base_image, original_img
    current_mode = None
    panel.config(cursor="")
    
    base_image = original_img.copy()
    reset_viewport(base_image)
    
    action_history = []
    current_step = 0
    render_state()
    update_button_states()

def ChangeImg():
    global base_image, original_img, action_history, current_step
    imgname = filedialog.askopenfilename(title="Change Image")
    if imgname:
        base_image = Image.open(imgname)
        original_img = base_image.copy() 
        reset_viewport(base_image)
        
        action_history = []
        current_step = 0
        render_state()
        update_button_states()

def save():
    global outputImage
    save_path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("All Files", "*.*")])
    if save_path:
        img_to_save = outputImage
        if save_path.lower().endswith((".jpg", ".jpeg")) and img_to_save.mode in ("RGBA", "P"):
            img_to_save = img_to_save.convert("RGB")
        img_to_save.save(save_path)

def close():
    mains.destroy()

# --- TKINTER GUI SETUP ---
mains = Tk()
space = (" ") * 215
screen_width = mains.winfo_screenwidth()
screen_height = mains.winfo_screenheight()

mains.geometry(f"{screen_width}x{screen_height}")
mains.title(f"{space}Image Editor")
mains.configure(bg='#323946')
mains.attributes("-fullscreen", True)

try:
    initial_img = Image.open("logo.png")
except FileNotFoundError:
    initial_img = Image.new('RGB', (600, 600), color='#323946')

original_img = initial_img.copy()
base_image = initial_img.copy()
img = initial_img.copy()
outputImage = initial_img.copy()

reset_viewport(base_image)

panel = Canvas(mains, width=600, height=600, bg='#323946', highlightthickness=0)
panel.grid(row=0, column=0, rowspan=12, padx=50, pady=50)

dim_label = Label(mains, text="", bg="#323946", fg="white", font=('poppins', 10, 'bold'))
dim_label.place(x=50, y=660)

coord_label = Label(mains, text="Cursor: X: 0, Y: 0 px", bg="#323946", fg="#00ffcc", font=('poppins', 10, 'bold'))
coord_label.place(x=350, y=660)

Label(mains, text="Mouse Wheel: Zoom  |  Right/Middle Drag: Pan", 
      bg="#323946", fg="gray", font=('poppins', 9, 'italic')).place(x=50, y=685)

# Input Bindings
panel.bind("<ButtonPress-1>", start_drag)
panel.bind("<B1-Motion>", drag)
panel.bind("<ButtonRelease-1>", end_drag)
panel.bind("<Motion>", track_mouse)

# Viewport Bindings
panel.bind("<MouseWheel>", zoom)
panel.bind("<Button-4>", zoom)
panel.bind("<Button-5>", zoom)
panel.bind("<ButtonPress-2>", start_pan)
panel.bind("<B2-Motion>", do_pan)
panel.bind("<ButtonPress-3>", start_pan)
panel.bind("<B3-Motion>", do_pan)

mains.bind("<Return>", apply_action)
mains.bind("<Escape>", cancel_action)

# --- UI WIDGETS ---
brightnessSlider = Scale(mains, label="Brightness", from_=0, to=2, orient=HORIZONTAL, length=200,
                         resolution=0.1, command=on_slider_move, bg="#1f242d")
brightnessSlider.set(1)
brightnessSlider.configure(font=('poppins',11,'bold'),foreground='white')
brightnessSlider.place(x=1070,y=15)
brightnessSlider.bind("<ButtonPress-1>", lambda e: on_slider_press('brightness', brightnessSlider))
brightnessSlider.bind("<ButtonRelease-1>", lambda e: on_slider_release('brightness', brightnessSlider))

contrastSlider = Scale(mains, label="Contrast", from_=0, to=2, orient=HORIZONTAL, length=200,
                       command=on_slider_move, resolution=0.1, bg="#1f242d")
contrastSlider.set(1)
contrastSlider.configure(font=('poppins',11,'bold'),foreground='white')
contrastSlider.place(x=1070,y=90)
contrastSlider.bind("<ButtonPress-1>", lambda e: on_slider_press('contrast', contrastSlider))
contrastSlider.bind("<ButtonRelease-1>", lambda e: on_slider_release('contrast', contrastSlider))

sharpnessSlider = Scale(mains, label="Sharpness", from_=0, to=2, orient=HORIZONTAL, length=200,
                        command=on_slider_move, resolution=0.1, bg="#1f242d")
sharpnessSlider.set(1)
sharpnessSlider.configure(font=('poppins',11,'bold'),foreground='white')
sharpnessSlider.place(x=1070,y=165)
sharpnessSlider.bind("<ButtonPress-1>", lambda e: on_slider_press('sharpness', sharpnessSlider))
sharpnessSlider.bind("<ButtonRelease-1>", lambda e: on_slider_release('sharpness', sharpnessSlider))

colorSlider = Scale(mains, label="Colors", from_=0, to=2, orient=HORIZONTAL, length=200,
                    command=on_slider_move, resolution=0.1, bg="#1f242d")
colorSlider.set(1)
colorSlider.configure(font=('poppins',11,'bold'),foreground='white')
colorSlider.place(x=1070,y=240)
colorSlider.bind("<ButtonPress-1>", lambda e: on_slider_press('color', colorSlider))
colorSlider.bind("<ButtonRelease-1>", lambda e: on_slider_release('color', colorSlider))

btnRotate = Button(mains, text='Rotate', width=25, command=rotate, bg="#1f242d")
btnRotate.configure(font=('poppins',11,'bold'),foreground='white')
btnRotate.place(x=805,y=110)

btnChaImg = Button(mains, text='Change Image', width=25,command=ChangeImg,bg="#1f242d",activebackground="ORANGE")
btnChaImg.configure(font=('poppins',11,'bold'),foreground='white')
btnChaImg.place(x=805,y=35)

btnFlip = Button(mains, text='Flip', width=25, command=flip, bg="#1f242d")
btnFlip.configure(font=('poppins',11,'bold'),foreground='white')
btnFlip.place(x=805,y=180)

btnResize = Button(mains, text='Resize', width=25, command=activate_resize, bg="#1f242d")
btnResize.configure(font=('poppins',11,'bold'),foreground='white')
btnResize.place(x=805,y=255)

btnCrop = Button(mains, text='Crop', width=25, command=activate_crop, bg="#1f242d")
btnCrop.configure(font=('poppins',11,'bold'),foreground='white')
btnCrop.place(x=805,y=340)

btnBlur = Button(mains, text='Blur', width=25, command=blurr, bg="#1f242d")
btnBlur.configure(font=('poppins',11,'bold'),foreground='white')
btnBlur.place(x=805,y=425)

btnEmboss = Button(mains, text='Emboss', width=25, command=emboss, bg="#1f242d")
btnEmboss.configure(font=('poppins',11,'bold'),foreground='white')
btnEmboss.place(x=805,y=510)

btnEdgeEnhance = Button(mains, text='EdgeEnhance', width=25, command=edgeEnhance, bg="#1f242d")
btnEdgeEnhance.configure(font=('poppins',11,'bold'),foreground='white')
btnEdgeEnhance.place(x=805,y=595)

btnSave = Button(mains, text='Save', width=25, command=save, bg="black")
btnSave.configure(font=('poppins',11,'bold'),foreground='white')
btnSave.place(x=805,y=675)

# --- TOP BAR BUTTONS ---
reset_button = Button(mains,text="Reset",command=reset,bg="black",activebackground="ORANGE")
reset_button.configure(font=('poppins',10,'bold'),foreground='white')
reset_button.place(x=380,y=15)

btnClose = Button(mains, text='Close', command=close, bg="black",activebackground="ORANGE")
btnClose.configure(font=('poppins',10,'bold'),foreground='white')
btnClose.place(x=440,y=15)

btnUndo = Button(mains, text='Undo', command=undo, bg="black", activebackground="ORANGE")
btnUndo.configure(font=('poppins',10,'bold'), foreground='white')
btnUndo.place(x=505, y=15)

btnRedo = Button(mains, text='Redo', command=redo, bg="black", activebackground="ORANGE")
btnRedo.configure(font=('poppins',10,'bold'), foreground='white')
btnRedo.place(x=565, y=15)

displayimage(img)
update_button_states()
mains.mainloop()