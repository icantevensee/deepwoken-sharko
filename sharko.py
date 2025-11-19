from ctypes import windll, wintypes, byref
import tkinter as tk
import random
import os
import pygame
import random
import math
import time
from pynput import keyboard, mouse
from PIL import Image, ImageDraw, ImageFont, ImageTk





class Sharko:
    WINDOW_SIZE = "357x342"
    ANIMATION_DELAY = 500
    TALKING_ANIMATION_DELAY = 10000
    IDLE_ANIMATION_DELAY = 25000
    GREETING_ANIMATION_DELAY = 8000
    REMOVAL_ANIMATION_DELAY = 5000
    INACTIVE_TIME_REQUIREMENT = 60

    

    IMAGES_PATH = "assets/sharko/"
    TALKING_SENTENCES_PATH = "assets/sentences/talking/"
    GREETING_SENTENCES_PATH = "assets/sentences/greeting/"
    REMOVAL_SENTENCES_PATH = "assets/sentences/removal/"
    END_TALKING_SOUND = "assets/sounds/end_talking.mp3"
    START_TALKING_SOUND = "assets/sounds/start_talking.mp3"
    CLASH_SOUND = "assets/sounds/Clash.mp3"
    GREETING_SOUND = "assets/sounds/greeting.mp3"
    FONT = r"TheFont.ttf"


    def __init__(self, image_path, talking_path, greeting_path, removal_path):
        file = open('Lines.txt', 'r')
        self.Lines = file.readlines()
        clean_lines = [line.strip() for line in self.Lines]
        self.Lines = clean_lines
        file.close()
        file = open('RemovalLines+IntroLine.txt', 'r')
        removalandintrolines = file.readlines()
        self.RemovalLines = []

        for index, line in enumerate(removalandintrolines):
            if index > 2:
                self.RemovalLines.append(line.strip())
            elif index == 1:
                self.IntroLine = line.strip()
        file.close()

        self.Quiet = False
        self.CutsceneIsPlaying = False
        self.Moviemode = False
        self.end = False
        self.Beingmoved = False
        self.geomreminder = False
        self.window = tk.Tk()
        self.sound_enabled = True
        pygame.init()
        self.Screen_x = self.window.winfo_screenwidth()
        self.Screen_y = self.window.winfo_screenheight()
        self.CurrentDirection = "Right"
        self.current_state = 'greeting'
        self.sound_file = self.GREETING_SOUND
        self.frame = 0
        self.min_volume = 0.1
        self.load_images(image_path, talking_path, greeting_path, removal_path)
        self.create_gui()
        self.animate()
        self.sounds(self.sound_file)
        self.add_talking_sentences(self.IntroLine.strip(),'greeting')
        self.window.after(self.GREETING_ANIMATION_DELAY, self.idle_state)
        #self.window.after(self.GREETING_ANIMATION_DELAY + self.IDLE_ANIMATION_DELAY + self.TALKING_ANIMATION_DELAY, self.idle_state)
        self.sound_paths = [self.END_TALKING_SOUND, self.START_TALKING_SOUND, self.GREETING_SOUND, self.CLASH_SOUND]
        self.sounds_group = [pygame.mixer.Sound(path) for path in self.sound_paths]
        self.Walking = False
        self.Walkspeed = 230 #Pixels per second

        screen_width = windll.user32.GetSystemMetrics(0)
        screen_height = windll.user32.GetSystemMetrics(1)
        SPI_GETWORKAREA = 0x0030
        desktop_working_area = wintypes.RECT()
        windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, byref(desktop_working_area), 0)
        work_area_height = desktop_working_area.bottom - desktop_working_area.top
        thickness_vertical = screen_height - work_area_height    
        if thickness_vertical > 0:
            TaskbarThick = thickness_vertical
        else:
            TaskbarThick = 0

        x = self.Screen_x-357
        y = self.Screen_y-342-TaskbarThick
        self.x = x
        self.y = y
        self.window.geometry(f"+{x}+{y}")
        self.last_input_time = time.time()

        keyboard_listener = keyboard.Listener(on_press=self.on_press)
        mouse_listener = mouse.Listener(on_move=self.on_click,on_click=self.on_click)

        keyboard_listener.start()
        mouse_listener.start()

        self.window.mainloop()
   
    

    def load_cutscenes(self):
                #Cutscene Format:
                #[image1, howlongtokeepimage1,sound], [image2, howlongtokeepimage2,sound], etc
                #["repeat",firstimage,secondimage, sound, timebetweentransitions, #transitions, Isthisfirstframe(just keep it true)] if you want it to repeat between 2 frames for dialouge
                #howlongtokeep & timebetweentransitions are in miliseconds
                self.CutscenePresets = {
            'InactiveCutscene': [[tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')), 1000, "None"],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'sideframe.png')), 150, "None"],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'staringframe.png')), 1000, "None"],
                     ["repeat",tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloSmall1.png')),tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloSmall2.png')), 1, 500, 10,True],
                     ["repeat",tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloBig1.png')),tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'HelloBig2.png')), 3, 500, 11,True],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'staringframe.png')), 1000, "None"],
                     [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'sideframe.png')), 150, "None"]],

        }


    def load_images(self, image_path, talking_path, greeting_path, removal_path):
        self.IMAGES_PATH = image_path
        self.TALKING_SENTENCES_PATH = talking_path
        self.GREETING_SENTENCES_PATH = greeting_path
        self.REMOVAL_SENTENCES_PATH = removal_path
        self.load_cutscenes()



        self.states = {
            'idle': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle2.png'))],
            'walking': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'walk1.png')),
                        tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'walk2.png'))],

            'talking': [],

            'greeting': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking1.png')),
                        tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking2.png'))],

            'MovieG': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'glasses1.png')),
                         tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'glasses2.png'))],
            
            'MovieNG': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')),
                     tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle2.png'))],

            'cutscene': [],

            'removal': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking1.png')),
                        tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'talking2.png'))],
        }


    def move_window_x(self,window, target_x):
        ANIMATION_DELAYOrig = self.ANIMATION_DELAY
        self.ANIMATION_DELAY = int(self.ANIMATION_DELAY/2)
        start_x = int(window.geometry().split('+')[-2])

        total_dx = target_x - start_x
        duration_ms = int(math.ceil(abs(total_dx)/self.Walkspeed)*1000)   
        FRAME_DELAY_MS = 16 
        num_steps = max(1, duration_ms // FRAME_DELAY_MS)
        step_dx = total_dx / num_steps
        def step_move(current_step, current_x):
            if self.end == True or self.Beingmoved == True:
                self.ANIMATION_DELAY = ANIMATION_DELAYOrig
                self.window.after(FRAME_DELAY_MS, self.idle_state)
                return

            if current_step >= num_steps:
                self.ANIMATION_DELAY = ANIMATION_DELAYOrig
                window.geometry(f'+{target_x}+{window.geometry().split('+')[-1]}')
                if self.CurrentDirection == "Right" :
                    self.window.after(FRAME_DELAY_MS, self.rotate_right)
                    self.window.after(FRAME_DELAY_MS+1, self.idle_state)
                else:
                    self.window.after(FRAME_DELAY_MS, self.rotate_left)
                    self.window.after(FRAME_DELAY_MS+1, self.idle_state)
                return

            new_x = int(current_x + step_dx)
            self.x = new_x
            window.geometry(f'+{new_x}+{window.geometry().split('+')[-1]}')
            window.after(FRAME_DELAY_MS, step_move, current_step + 1, current_x + step_dx)
        window.after(FRAME_DELAY_MS, step_move, 0, start_x)
        

    def create_gui(self):
        self.label = tk.Label(self.window, bd=0, bg='#2a2d2a')
        self.label.configure(image=self.states['idle'][0])
        self.label.image = self.states['idle'][0]
        self.label.pack()

        self.menu = tk.Menu(self.window, tearoff=0)
        self.Movie_menu = tk.Menu(self.window, tearoff=0)
        self.Movie_menu.add_command(label='Off', command=self.MovieOff)
        self.Movie_menu.add_command(label='On(Glasses)', command=self.MovieOn)
        self.Movie_menu.add_command(label='On(No glasses)', command=self.MovieOn1)
        self.menu.add_cascade(label='Movie mode', menu=self.Movie_menu)
        self.menu.add_command(label='Sounds (Off/On)', command=self.sounds_logics)
        self.menu.add_command(label='Close', command=self.close_command)

        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.wm_attributes('-transparentcolor', '#2a2d2a')
        self.window.geometry(self.WINDOW_SIZE)
        


        self.label.bind("<ButtonPress-2>", self.move1)
        self.label.bind("<ButtonRelease-2>", self.release)
        self.label.bind("<B2-Motion>", self.move2)
        self.label.bind("<Double-Button-2>", lambda event: self.menu.post(event.x_root, event.y_root))


    def animate(self):
        if self.geomreminder == True:
            self.geomreminder = False
            if self.CurrentDirection == "Left":
                self.window.geometry(f'+{0}+{self.window.geometry().split('+')[-1]}')
            else: 
                self.window.geometry(f'+{self.Screen_x-359}+{self.window.geometry().split('+')[-1]}')

        if self.CutsceneIsPlaying == True:
            return
        state_images = self.states[self.current_state]
        self.frame = (self.frame + 1) % len(state_images)
        self.label.configure(image=state_images[self.frame])
        self.label.image = state_images[self.frame]

        self.window.after(self.ANIMATION_DELAY, self.animate)

    def play_cutscene(self, cutscenepreset):
        if self.CutsceneIsPlaying == True:
            return
        self.CutsceneIsPlaying = True
        self.new_state('cutscene')
        Cutscene = self.CutscenePresets[cutscenepreset]
        self.PlayCutsceneFrame(Cutscene, 0,cutscenepreset)


    def PlayCutsceneFrame(self, Cutscene, Currentframe,cutscenepreset):
        if cutscenepreset== 'InactiveCutscene':
            if time.time()-self.last_input_time < self.INACTIVE_TIME_REQUIREMENT:
                if Currentframe <6:
                    Currentframe = 6 
                elif Currentframe == len(Cutscene):
                    self.CutsceneIsPlaying = False
                    self.Quiet = False
                    self.load_cutscenes()
                    self.idle_state()
                    self.animate()
                    return
            elif Currentframe == len(Cutscene):
                self.CutsceneIsPlaying = False
                self.Quiet = True
                self.load_cutscenes()
                self.idle_state()
                self.animate()
                return


        if Currentframe == len(Cutscene):
            self.CutsceneIsPlaying = False
            self.load_cutscenes()
            self.idle_state()
            self.animate()
            return
            


        
        CurrentFrameInfo = Cutscene[Currentframe]
        if CurrentFrameInfo[0] == "repeat":
            Image = CurrentFrameInfo[1]
            Time = CurrentFrameInfo[4]
            Sound = CurrentFrameInfo[3]
            CurrentFrameInfo[5] = CurrentFrameInfo[5]-1
            FF = CurrentFrameInfo[6]
            CurrentFrameInfo[6] = False
            CurrentFrameInfo[1], CurrentFrameInfo[2] = CurrentFrameInfo[2], CurrentFrameInfo[1]
            if CurrentFrameInfo[5] == 0 :
                Currentframe = Currentframe + 1
        else:
            Image = CurrentFrameInfo[0]
            Time = CurrentFrameInfo[1]
            Sound = CurrentFrameInfo[2]
            Currentframe = Currentframe + 1
            FF = True
        if Sound != "None" and FF == True:
            Soundfile = self.sound_paths[Sound]
            self.sounds(Soundfile)
        self.label.configure(image=Image)
        self.label.image = Image
        self.window.after(Time, self.PlayCutsceneFrame,Cutscene,Currentframe,cutscenepreset)


        



    def clear_talking(self,state):
        # remove any talking state frames and any overlay label we created
        self.states[state] = []
        if hasattr(self, 'talk_overlay') and self.talk_overlay is not None:
            try:
                self.talk_overlay.destroy()
            except Exception:
                pass
            self.talk_overlay = None


    def move1(self, event):
        self.y = event.y
        self.x = event.x
        self.Beingmoved = True

    def release(self, event):
        self.y = event.y
        self.Beingmoved = False


    def move2(self, event):
        x = self.window.winfo_pointerx() - self.x
        y = self.window.winfo_pointery() - self.y
        self.window.geometry(f"+{x}+{y}")


    def new_state(self, new_state):
        self.current_state = new_state

    def MovieOff(self):
        self.Moviemode = False
        self.idle_state()

    def MovieOn(self):
        self.Moviemode = True
        self.new_state('MovieG')
    
    def MovieOn1(self):
        self.Moviemode = True
        self.new_state('MovieNG')


    def on_press(self):
        self.last_input_time = time.time()
        self.Quiet = False

    def on_click(self):
        self.last_input_time = time.time()
        self.Quiet = False


    def talking_state(self):
        if self.current_state == 'idle':
            self.add_talking_sentences(random.choice(self.Lines).strip(),'talking')
            self.new_state('talking')
            sound_file = self.START_TALKING_SOUND
            self.sounds(sound_file)
        self.window.after(self.TALKING_ANIMATION_DELAY, self.idle_state)

    
    def idle_state(self):
        if self.current_state == 'talking' or self.current_state == 'cutscene' and self.CutsceneIsPlaying == False or self.current_state == 'greeting'or self.current_state == 'walking' or self.current_state == 'MovieG' and self.Moviemode == False or self.current_state == 'MovieNG' and self.Moviemode == False:
            if not self.current_state == 'walking' and not self.current_state == 'cutscene':
                sound_file = self.END_TALKING_SOUND
                self.sounds(sound_file)
            self.new_state('idle')
            self.clear_talking('talking')
            if time.time()-self.last_input_time > self.INACTIVE_TIME_REQUIREMENT and self.Quiet == False:
                self.Quiet = True
                self.play_cutscene('InactiveCutscene')
            else:
                random_integer = random.randint(1, 20)
                if random_integer > 3 and self.Quiet == False or self.Beingmoved == True :
                    self.window.after(self.IDLE_ANIMATION_DELAY, self.talking_state)
                else:
                    self.window.after(self.IDLE_ANIMATION_DELAY, self.walking_state)

    def walking_state(self):
         if self.current_state == 'idle':
            self.new_state('walking')

            state_images = self.states[self.current_state]
            self.frame = (self.frame + 1) % len(state_images)
            self.label.configure(image=state_images[self.frame])
            self.label.image = state_images[self.frame]
            if self.CurrentDirection == "Right":
                self.move_window_x(self.window, -179)
            else:
                self.move_window_x(self.window, self.Screen_x-179)



    def add_talking_sentences(self,sentence,state):


        if not hasattr(self, 'Lines') or not self.Lines:
            return



        box_w, box_h = 255, 140

        def render_text_image(text, size):
            img = Image.new('RGBA', (size[0], size[1]), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            base_font_path = self.FONT
            """try:
                if isinstance(self.FONT, str) and os.path.isfile(self.FONT):
                    base_font_path = self.FONT
                elif os.path.exists(r"C:\Windows\Fonts\"):
                    base_font_path = r"C:\Windows\Fonts\arial.ttf"
            except Exception:
                base_font_path = None"""


            padding = 0
            line_spacing = 8 


            for font_size in range(72, 7, -1):
                font = ImageFont.truetype(base_font_path, font_size)


                words = text.split()
                lines = []
                cur = ''
                for w in words:
                    test = (cur + ' ' + w).strip()
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
                        bbox = draw.textbbox((0, 0), 'Mg', font=font)
                        single_line_h = bbox[3] - bbox[1]
                    except Exception:
                        single_line_h = 12
                total_h = single_line_h * len(lines) + (len(lines)-1) * line_spacing
                if total_h <= size[1] - padding * 2:
                    y = 0
                    for i, l in enumerate(lines):
                        bbox = draw.multiline_textbbox((0, 0), l, font=font)
                        tw = bbox[2] - bbox[0]
                        x = 0
                        draw.text((x, y), l, font=font, fill=(0, 0, 0, 255))
                        y += single_line_h + line_spacing
                    return img

            draw.text((0, 0), text, font=ImageFont.load_default(), fill=(0,0,0,255))
            return img

        text_img = render_text_image(sentence, (box_w, box_h))
        try:
            base1_path = os.path.join(self.IMAGES_PATH, 'talking1.png')
            base2_path = os.path.join(self.IMAGES_PATH, 'talking2.png')
            base1 = Image.open(base1_path).convert('RGBA')
            base2 = Image.open(base2_path).convert('RGBA')
        except Exception:
            try:
                tk_img = ImageTk.PhotoImage(text_img)
            except Exception:
                return
            self.states['talking'].extend([tk_img, tk_img])
            return

        def composite_on_base(base_img):
            b = base_img.copy()
            bw, bh = b.size
            if self.CurrentDirection == "Left":
                x = 97
            else:
                x = 9
            y = 9
            b.paste(text_img, (x, y), text_img)
            return b

        comp1 = composite_on_base(base1)
        comp2 = composite_on_base(base2)

        try:
            tk_img1 = ImageTk.PhotoImage(comp1)
            tk_img2 = ImageTk.PhotoImage(comp2)
        except Exception:
            return

        self.states[state] = [tk_img1, tk_img2]

    
    def add_removal_sentences(self):
        self.add_talking_sentences(random.choice(self.RemovalLines).strip(),'removal')


    def close_command(self):
        self.end = True
        if self.current_state != 'removal' and self.current_state != 'cutscene':
            self.add_removal_sentences()
            self.new_state('removal')
        if self.current_state == 'removal':
            pass
        
        self.window.after(self.REMOVAL_ANIMATION_DELAY, Sharko.exit)
        
        
    def exit():
        os._exit(0)


    def restart_application(self, new_image_path, new_talking_path, new_greeting_path, new_removal_path):
        self.window.destroy()
        Sharko(new_image_path, new_talking_path, new_greeting_path, new_removal_path)
    

    def rotate_right(self):

        new_image_path = "assets/mirror_sharko/"
        new_talking_path = "assets/mirror_sentences/talking/"
        new_greeting_path = "assets/mirror_sentences/greeting/"
        new_removal_path = "assets/mirror_sentences/removal/"
        self.load_images(new_image_path,new_talking_path,new_greeting_path,new_removal_path)
        self.CurrentDirection = "Left"
        self.x = 0
        self.geomreminder = True
        

    def rotate_left(self):
        new_image_path = "assets/sharko/"
        new_talking_path = "assets/sentences/talking/"
        new_greeting_path = "assets/sentences/greeting/"
        new_removal_path = "assets/sentences/removal/"
        self.load_images(new_image_path,new_talking_path,new_greeting_path,new_removal_path)
        self.CurrentDirection = "Right"
        self.x = self.Screen_x-359

        self.geomreminder = True





    def sounds(self, sound_file):
        pygame.mixer.init()
        pygame.mixer.music.load(sound_file)
        if self.sound_enabled:
            pygame.mixer.music.set_volume(1.0)
        else:
            pygame.mixer.music.set_volume(0.0)
        pygame.mixer.music.play()

    
    def sounds_logics(self):
        self.sound_enabled = not self.sound_enabled
        if not self.sound_enabled:
            for sound in self.sounds_group:
                sound.set_volume(0.0)  
        else:
            for sound in self.sounds_group:
                sound.set_volume(1.0) 









        

sharko = Sharko("assets/sharko/",
                "assets/sentences/talking/",
                "assets/sentences/greeting/",
                "assets/sentences/removal/")


sharko.window.mainloop()

