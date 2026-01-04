from ctypes import windll, wintypes, byref
import ctypes
import tkinter as tk
import random
import os
import pygame
import math
import time
from pynput import keyboard, mouse
from PIL import Image, ImageDraw, ImageFont, ImageTk
import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QPixmap, QPainter, QImage
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap

import ctypes
# Make Tkinter aware of Windows DPI scaling
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class Sharko:
    FADE_STEP = 1
    WINDOW_SIZE = "357x342"
    ANIMATION_DELAY = 500
    TALKING_ANIMATION_DELAY = 10000
    IDLE_ANIMATION_DELAY = 20000
    GREETING_ANIMATION_DELAY = 8000
    REMOVAL_ANIMATION_DELAY = 3800
    INACTIVE_TIME_REQUIREMENT = 60

    

    IMAGES_PATH = "assets/sharko/"
    TALKING_SENTENCES_PATH = "assets/sentences/talking/"
    GREETING_SENTENCES_PATH = "assets/sentences/greeting/"
    REMOVAL_SENTENCES_PATH = "assets/sentences/removal/"
    END_TALKING_SOUND = "assets/sounds/end_talking.mp3"
    START_TALKING_SOUND = "assets/sounds/start_talking.mp3"
    CLASH_SOUND = "assets/sounds/Clash.mp3"
    GREETING_SOUND = "assets/sounds/greeting.mp3"
    ANSWER_SOUND = "assets/sounds/answer_question.mp3"

    FONT = r"TheFont.ttf"


    def __init__(self, image_path, talking_path, greeting_path, removal_path):
        self._idle_after_id = None
        try:
            file = open('Lines.txt', 'r', encoding='utf-8')
            self.Lines = file.readlines()
            clean_lines = [self._decode_escapes(line.strip()) for line in self.Lines]
            self.Lines = clean_lines
        except Exception:
            try:
                file = open('Lines.txt', 'r')
                self.Lines = [line.strip() for line in file.readlines()]
            except Exception:
                self.Lines = []
        finally:
            try:
                file.close()
            except Exception:
                pass
        file = open('RemovalLines+IntroLine.txt', 'r', encoding='utf-8')
        removalandintrolines = file.readlines()
        self.RemovalLines = []

        for index, line in enumerate(removalandintrolines):
            decoded = self._decode_escapes(line.strip())
            if index > 2:
                self.RemovalLines.append(decoded)
            elif index == 1:
                self.IntroLine = decoded
        file.close()

        file = open('Questions.txt', 'r', encoding='utf-8')
        removalandintrolines = file.readlines()
        self.Questions = []
        for index, line in enumerate(removalandintrolines):
            decoded = self._decode_escapes(line.strip())
            Current_Question = math.floor(index/5)
            Current_Line  = index - Current_Question*5
            if Current_Line == 0:
                self.Questions.append([])
            self.Questions[Current_Question].append(decoded)
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
        self.add_talking_sentences(self.IntroLine.strip(),'greeting',False)
        self.window.after(self.GREETING_ANIMATION_DELAY, self.idle_state)
        self.sound_paths = [self.END_TALKING_SOUND, self.START_TALKING_SOUND, self.GREETING_SOUND, self.CLASH_SOUND, self.ANSWER_SOUND]
        self.sounds_group = [pygame.mixer.Sound(path) for path in self.sound_paths]
        self.Walking = False
        self.Walkspeed = 230 #Pixels per second
        self.walking_enabled = True

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



    def _decode_escapes(self, s):

        if not isinstance(s, str):
            return s
        if ('\\u' in s) or ('\\x' in s) or ('\\U' in s) or ('&#' in s) or ('&' in s):
            try:
                decoded = s.encode('utf-8').decode('unicode_escape')
            except Exception:
                decoded = s
            try:
                import html
                decoded = html.unescape(decoded)
            except Exception:
                pass
            return decoded
        return s
   
    

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
            'Limbo': [tk.PhotoImage(file=os.path.join(self.IMAGES_PATH, 'idle1.png')),
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
        self.menu.add_command(label='Walking (Off/On)', command=self.toggle_walking)
        self.menu.add_command(label='Flip side', command=self.flip_side)
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
        if self.label.image == None:
            return
        if self.geomreminder == True:
            self.geomreminder = False
            if self.CurrentDirection == "Left":
                self.window.geometry(f'+{0}+{self.window.geometry().split('+')[-1]}')
            else: 
                self.window.geometry(f'+{self.Screen_x-359}+{self.window.geometry().split('+')[-1]}')

        if self.CutsceneIsPlaying == True:
            return
        state_images = self.states.get(self.current_state, [])
        if not state_images:
            state_images = self.states.get('idle', [])
            if not state_images:
                self.window.after(self.ANIMATION_DELAY, self.animate)
                return
            self.current_state = 'idle'

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
        self.states[state] = []
        if hasattr(self, 'talk_overlay') and self.talk_overlay is not None:
            try:
                self.talk_overlay.destroy()
            except Exception:
                pass
            self.talk_overlay = None
        if getattr(self, 'question_active', False):
            self.question_active = False
            self._question_answers = None
            try:
                self.label.unbind("<Button-1>")
            except Exception:
                pass


    def move1(self, event):
        self.y = event.y
        self.x = event.x
        self.Beingmoved = True

    def _handle_question_click(self, event):
        if not getattr(self, 'question_active', False):
            return
        x_off = 97 if self.CurrentDirection == "Left" else 9
        x = event.x
        y = event.y
        if x >= x_off and x <= x_off + 255 and y >= 96 and y <= 126:
            answer_text = self._question_answers[0] if self._question_answers else None
            if answer_text:
                sound_file = self.ANSWER_SOUND
                self.sounds(sound_file)
                self._display_answer(answer_text)
        elif x >= x_off and x <= x_off + 255 and y >= 126 and y <= 163:
            answer_text = self._question_answers[1] if self._question_answers else None
            if answer_text:
                sound_file = self.ANSWER_SOUND
                self.sounds(sound_file)
                self._display_answer(answer_text)

    def _display_answer(self, answer_text):
        self.question_active = False
        self._question_answers = None
        try:
            self.label.unbind("<Button-1>")
        except Exception:
            pass
        try:
            if getattr(self, '_idle_after_id', None) is not None:
                self.window.after_cancel(self._idle_after_id)
        except Exception:
            pass
        self.add_talking_sentences(answer_text, 'talking', False)
        self.new_state('talking')
        try:
            self._idle_after_id = self.window.after(self.TALKING_ANIMATION_DELAY, self.idle_state)
        except Exception:
            self._idle_after_id = None


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

    def toggle_walking(self):
        """Toggle automatic walking on/off from the middle-click menu."""
        self.walking_enabled = not self.walking_enabled
        if not self.walking_enabled and self.current_state == 'walking':
            self.Beingmoved = True
            try:
                self.window.after(50, self._stop_walk_cleanup)
            except Exception:
                self._stop_walk_cleanup()

    def _stop_walk_cleanup(self):
        self.Beingmoved = False
        if self.current_state == 'walking':
            self.new_state('idle')

    def flip_side(self):
        try:
            if self.CurrentDirection == 'Right':
                self.rotate_right()
                try:
                    y = self.window.geometry().split('+')[-1]
                except Exception:
                    y = self.window.winfo_y()
                self.window.geometry(f'+{0}+{y}')
                self.x = 0
            else:
                self.rotate_left()
                right_x = max(0, self.Screen_x - int(self.WINDOW_SIZE.split('x')[0]))
                try:
                    y = self.window.geometry().split('+')[-1]
                except Exception:
                    y = self.window.winfo_y()
                self.window.geometry(f'+{right_x}+{y}')
                self.x = right_x
            self.window.lift()
            self.geomreminder = True
        except Exception:
            pass



    def on_press(self):
        self.last_input_time = time.time()
        self.Quiet = False

    def on_click(self):
        self.last_input_time = time.time()
        self.Quiet = False


    def talking_state(self):
        if self.current_state == 'idle':
            
            Line = random.choice(self.Lines + self.Questions)

            if isinstance(Line, str):
                self.add_talking_sentences(Line.strip(),'talking',False)
                self.new_state('talking')
            else:
                self.add_new_question(Line)
                self.new_state('talking')

            sound_file = self.START_TALKING_SOUND
            self.sounds(sound_file)
        try:
            if getattr(self, '_idle_after_id', None) is not None:
                self.window.after_cancel(self._idle_after_id)
        except Exception:
            pass
        self._idle_after_id = self.window.after(self.TALKING_ANIMATION_DELAY, self.idle_state)

    
    def idle_state(self):
        try:
            self._idle_after_id = None
        except Exception:
            pass
        if self.current_state == 'talking' or self.current_state == 'cutscene' and self.CutsceneIsPlaying == False or self.current_state == 'greeting'or self.current_state == 'walking' or self.current_state == 'MovieG' and self.Moviemode == False or self.current_state == 'MovieNG' and self.Moviemode == False or self.current_state == 'Limbo':
            if not self.current_state == 'walking' and not self.current_state == 'cutscene' and not self.current_state == 'Limbo':
                sound_file = self.END_TALKING_SOUND
                self.sounds(sound_file)
            self.new_state('idle')
            self.clear_talking('talking')
            if time.time()-self.last_input_time > self.INACTIVE_TIME_REQUIREMENT and self.Quiet == False:
                self.Quiet = True
                self.play_cutscene('InactiveCutscene')
            else:
                random_integer = random.randint(1, 20)
                if random_integer > 3 and self.Quiet == False or self.Beingmoved == True or self.walking_enabled == False and self.Quiet == False:
                    self.window.after(self.IDLE_ANIMATION_DELAY, self.talking_state)
                else:
                    if self.walking_enabled == False and self.Quiet == True:
                        self.current_state = 'Limbo'
                        self.window.after(self.IDLE_ANIMATION_DELAY, self.idle_state)
                    else:
                        self.window.after(self.IDLE_ANIMATION_DELAY, self.walking_state)

    def walking_state(self):
        if self.current_state == 'idle':
            self.new_state('walking')

            state_images = self.states.get(self.current_state, [])
            if not state_images:
                return
            self.frame = (self.frame + 1) % len(state_images)
            self.label.configure(image=state_images[self.frame])
            self.label.image = state_images[self.frame]
            if self.CurrentDirection == "Right":
                self.move_window_x(self.window, -179)
            else:
                self.move_window_x(self.window, self.Screen_x-179)

    def add_new_question(self,Question_Lines):
        self.add_talking_sentences(Question_Lines,'talking',3)




    def add_talking_sentences(self,sentence,state,IsQuestion):


        if not hasattr(self, 'Lines') or not self.Lines:
            return


        
        box_w, box_h = 255, 140

        def render_text_image(text, size):
            img = Image.new('RGBA', (size[0], size[1]), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            base_font_path = self.FONT

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

        if IsQuestion == 3:
            try:
                question_text = sentence[0]
                option1_text = sentence[1]
                option2_text = sentence[2]
                answer1_text = sentence[3]
                answer2_text = sentence[4]
            except Exception:
                return

            q_img = render_text_image(question_text, (255, 80))
            opt1_img = render_text_image(option1_text, (255, 30))
            opt2_img = render_text_image(option2_text, (255, 30))

            try:
                base1_path = os.path.join(self.IMAGES_PATH, 'talking1.png')
                base2_path = os.path.join(self.IMAGES_PATH, 'talking2.png')
                base1 = Image.open(base1_path).convert('RGBA')
                base2 = Image.open(base2_path).convert('RGBA')
            except Exception:
                try:
                    combined = Image.new('RGBA', (255, 140), (0, 0, 0, 0))
                    combined.paste(q_img, (0, 9), q_img)
                    combined.paste(opt1_img, (0, 96), opt1_img)
                    combined.paste(opt2_img, (0, 126), opt2_img)
                    tk_img = ImageTk.PhotoImage(combined)
                    self.states[state] = [tk_img, tk_img]
                    self._question_answers = (answer1_text, answer2_text)
                    self.question_active = True
                    try:
                        self.label.bind("<Button-1>", self._handle_question_click)
                    except Exception:
                        pass
                except Exception:
                    return
                return

            def composite_three(base_img):
                b = base_img.copy()
                if self.CurrentDirection == "Left":
                    x = 97
                else:
                    x = 9
                b.paste(q_img, (x, 9), q_img)
                b.paste(opt1_img, (x, 96), opt1_img)
                b.paste(opt2_img, (x, 126), opt2_img)
                return b

            comp1 = composite_three(base1)
            comp2 = composite_three(base2)

            try:
                tk_img1 = ImageTk.PhotoImage(comp1)
                tk_img2 = ImageTk.PhotoImage(comp2)
            except Exception:
                return

            self.states[state] = [tk_img1, tk_img2]
            self._question_answers = (answer1_text, answer2_text)
            self.question_active = True
            try:
                self.label.bind("<Button-1>", self._handle_question_click)
            except Exception:
                pass
            return

        

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
            if IsQuestion == 1:
                y = 96
            elif IsQuestion == 2:
                y = 126
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
        self.add_talking_sentences(random.choice(self.RemovalLines).strip(),'removal',False)


    def close_command(self):
        self.end = True
        if self.current_state != 'removal' and self.current_state != 'cutscene':
            self.add_removal_sentences()
            self.new_state('removal')
        if not getattr(self, '_death_scheduled', False):
            self._death_scheduled = True
            self.window.after(self.REMOVAL_ANIMATION_DELAY, self.death_animation)


    def exit():
        os._exit(0)



    def death_animation(self):
        Screen_x,Screen_y = self.window.winfo_x(), self.window.winfo_y()

        window = self.window

        TILE_SIZE = 15


        class DeathAnimationWidget(QWidget):

            def __init__(self, src_path):
                super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
                self.setAttribute(Qt.WA_TranslucentBackground)
                self.setWindowFlag(Qt.WindowStaysOnTopHint)
                self.setWindowFlag(Qt.Tool)
                self.setWindowFlag(Qt.FramelessWindowHint)
                self.tiles = []
                self.firstime = True
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.animate)
                self.load_tiles(src_path)
                src_path.size = (357, 342)
                self.resize(self.img_w, self.img_h)
                self.setGeometry(Screen_x,Screen_y-600, self.img_w, self.img_h)
                self.setFixedSize(500,2000)
                self.show()
                self.timer.start(16)


            def load_tiles(self, src_path):

                src = src_path
                self.img_w = src.width()
                self.img_h = src.height()
                for y in range(0, self.img_h, TILE_SIZE):
                    for x in range(0, self.img_w, TILE_SIZE):
                        tile_img = src.copy(x, y, TILE_SIZE, TILE_SIZE)
                        if tile_img.hasAlphaChannel():
                            self.tiles.append(Tile(QPixmap.fromImage(tile_img), x, y))

            def animate(self):
                for tile in self.tiles:
                    tile.update()
                self.tiles = [t for t in self.tiles if t.alpha > 0]
                if not self.tiles:
                    os._exit(0)
                self.update()
                if self.firstime == True:
                    window.withdraw()
                    self.firstime = False

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)
                for tile in self.tiles:
                    painter.save()
                    painter.setOpacity(tile.alpha / 255.0)
                    painter.translate(tile.x + TILE_SIZE // 2, tile.y + TILE_SIZE // 2)
                    painter.rotate(tile.angle)
                    painter.translate(-TILE_SIZE // 2, -TILE_SIZE // 2)
                    painter.drawPixmap(0, 0, tile.img)
                    painter.restore()

        if __name__ == '__main__':
            app = QApplication(sys.argv)
            if len(sys.argv) > 1:
                img_path = sys.argv[1]
                img_path = state_images[self.frame]
                img_path = ImageTk.getimage(img_path)
            else:
                state_images = self.states.get(self.current_state, [])
                img_path = state_images[self.frame]
                img_path = ImageTk.getimage(img_path)
                img = img_path.convert("RGBA")
                r, g, b, a = img.split()
                bgra = Image.merge("RGBA", (b, g, r, a))
                buf = bgra.tobytes("raw", "RGBA")
                w,h = img.size
                qimg = QImage(buf, w ,h , 4*w, QImage.Format_ARGB32)
                qimg._buf = buf
            w = DeathAnimationWidget(qimg)
            sys.exit(app.exec_())


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
        try:
            self.new_state('Limbo')
        except Exception:
            pass
        

    def rotate_left(self):
        new_image_path = "assets/sharko/"
        new_talking_path = "assets/sentences/talking/"
        new_greeting_path = "assets/sentences/greeting/"
        new_removal_path = "assets/sentences/removal/"
        self.load_images(new_image_path,new_talking_path,new_greeting_path,new_removal_path)
        self.CurrentDirection = "Right"
        self.x = self.Screen_x-359

        self.geomreminder = True
        try:
            self.new_state('Limbo')
        except Exception:
            pass





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


class Tile:
        def __init__(self, img, x, y):
            self.img = img
            self.x = x
            self.y = y+600
            self.vx = random.uniform(-0.2, 0.2)
            self.vy = random.uniform(-2, -0.4)
            self.alpha = 255
            self.angle = 0
            self.angvel = random.uniform(-8, 8)

        def update(self):
            self.x += self.vx
            self.y += self.vy
            self.angle = (self.angle + self.angvel) % 360
            self.alpha = max(0, int(self.alpha) - Sharko.FADE_STEP)






        

sharko = Sharko("assets/sharko/",
                "assets/sentences/talking/",
                "assets/sentences/greeting/",
                "assets/sentences/removal/")


sharko.window.mainloop()

