"""
Constants and configuration for Sharko application
"""

class SharkoConstants:
    """Class constants and configuration"""
    
    # Animation/timing
    FADE_STEP = 1
    ANIMATION_DELAY = 500
    TALKING_ANIMATION_DELAY = 10000
    IDLE_ANIMATION_DELAY = 20000
    GREETING_ANIMATION_DELAY = 8000
    REMOVAL_ANIMATION_DELAY = 3800
    INACTIVE_TIME_REQUIREMENT = 60
    
    # Window
    WINDOW_SIZE = "357x342"
    
    # Paths
    ASSETS_PATH = "assets/"
    IMAGES_PATH = "assets/sharko/"
    ALT_1IMAGES_PATH = "assets/mirror_sharko"
    BAR_IMG_PATH = "assets/UI/boss_bar_border.png"
    MARKER_PATH = "assets/UI/boss_bar_pins.png"
    CENTER_ICON_PATH = "assets/UI/boss_bar_skull.png"
    FONT_PATH = "assets/fonts/Boss_Font.otf"
    TALKING_SENTENCES_PATH = "assets/sentences/talking/"
    GREETING_SENTENCES_PATH = "assets/sentences/greeting/"
    REMOVAL_SENTENCES_PATH = "assets/sentences/removal/"
    
    # Sounds
    END_TALKING_SOUND = "assets/sounds/end_talking.mp3"
    START_TALKING_SOUND = "assets/sounds/start_talking.mp3"
    CLASH_SOUND = "assets/sounds/Clash.mp3"
    GREETING_SOUND = "assets/sounds/greeting.mp3"
    ANSWER_SOUND = "assets/sounds/answer_question.mp3"
    
    # Fonts
    FONT = r"assets/fonts/TheFont.ttf"
    
    # COM interfaces
    CLSID_ShellWindows = "{9BA05972-F6A8-11CF-A442-00A0C90A8F39}"
    IID_IFolderView = "{CDE725B0-CCC9-4519-917E-325D72FAB4CE}"
    
    # Windows API constants
    SWC_DESKTOP = 0x08
    SWFO_NEEDDISPATCH = 0x01
    SPI_GETWORKAREA = 0x0030
    LVM_SETITEMPOSITION = 0x100F
    LVM_GETITEMCOUNT = 0x1004
